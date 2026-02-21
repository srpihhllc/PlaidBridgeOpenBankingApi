# app/security_utilities.py
"""
Security and operational utilities.
- Exposes stable import points for MFA send helpers (check_mfa_send_rate_limit,
  record_mfa_send_request).
- If real implementations are present, prefer them; otherwise provide safe,
  well-logged fallbacks.
- Contains lightweight mock infrastructure (Redis, DB, synthetic probe) used by
  health checks and tests.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, cast

logger = logging.getLogger(__name__)

# Constants for the default MFA Rate Limiting implementation (used in fallback)
MFA_LIMIT_WINDOW_SECONDS = 60  # 1 minute
MFA_REQUEST_LIMIT = 3  # Max 3 requests per window

# -----------------------------------------------------------------------
# Canonical import shim for MFA helpers (single definition only)
# - Try likely real locations first; fall back to mock implementations for local testing.
# - Keep this as the single source of truth to avoid redefinitions.
# -----------------------------------------------------------------------
try:
    # Primary expected location
    from app.services.mfa_helpers import check_mfa_send_rate_limit, record_mfa_send_request
except Exception:
    try:
        # Alternate common location
        from app.services.security_helpers import check_mfa_send_rate_limit, record_mfa_send_request
    except Exception:
        # --- FALLBACK: MFA SEND RATE LIMITING (Mock Implementation using MockRedisClient) ---

        def check_mfa_send_rate_limit(user_id: str | None, ip_address: str | None = None) -> bool:
            """
            Fallback rate-limit check, using Mock Redis client for local environment
            testing. Returns True when allowed, False when rate-limited. Fail-open
            if Redis is unavailable.
            """
            client = get_redis_client()
            if not client:
                logger.debug(
                    "Fallback check_mfa_send_rate_limit called for user_id=%s ip=%s — "
                    "real implementation not found (Mock Redis unavailable)",
                    user_id,
                    ip_address,
                )
                return True

            # Check user limit
            if user_id:
                user_key = f"rate:mfa_send:user:{user_id}"
                user_count_str = client.get(user_key)
                user_count = int(user_count_str) if user_count_str else 0
                if user_count >= MFA_REQUEST_LIMIT:
                    logger.warning(
                        "Rate limit exceeded for User ID %s (Count: %s)",
                        user_id,
                        user_count,
                    )
                    return False

            # Check IP limit
            if ip_address:
                ip_key = f"rate:mfa_send:ip:{ip_address}"
                ip_count_str = client.get(ip_key)
                ip_count = int(ip_count_str) if ip_count_str else 0
                if ip_count >= MFA_REQUEST_LIMIT:
                    logger.warning(
                        "Rate limit exceeded for IP Address %s (Count: %s)",
                        ip_address,
                        ip_count,
                    )
                    return False

            return True

        def record_mfa_send_request(
            user_id: str | None,
            ip_address: str | None = None,
            channel: str = "sms",
            masked_dest: str | None = None,
        ) -> None:
            """
            Fallback recorder, increments counters using atomic-like semantics for
            local testing. Accepts all channel/dest arguments for compatibility,
            but only logs them. No-op if Redis unavailable.
            """
            client = get_redis_client()
            if not client:
                logger.debug(
                    "Fallback record_mfa_send_request called user_id=%s ip=%s "
                    "channel=%s dest=%s — real implementation not found (Mock Redis "
                    "unavailable)",
                    user_id,
                    ip_address,
                    channel,
                    masked_dest,
                )
                return

            window = MFA_LIMIT_WINDOW_SECONDS

            # Use incr_with_expire to simulate atomic INCR+EXPIRE (create-with-ttl when count==1)
            if user_id:
                user_key = f"rate:mfa_send:user:{user_id}"
                client.incr_with_expire(user_key, window)

            if ip_address:
                ip_key = f"rate:mfa_send:ip:{ip_address}"
                client.incr_with_expire(ip_key, window)

            logger.debug(
                "Fallback record_mfa_send_request recorded user_id=%s ip=%s channel=%s dest=%s",
                user_id,
                ip_address,
                channel,
                masked_dest,
            )


# =========================================================================
# --- MOCKING DEPENDENCIES (Redis Client, DB, User Model) ---
# This simulates external components for synthetic probes and local tests.
# =========================================================================


class MockRedisClient:
    """
    Mock Redis client for demonstration and local tests, simulating K/V, TTL, and lists.
    Includes incr_with_expire to simulate atomic INCR+EXPIRE semantics used for robust
    rate limiting.
    """

    def __init__(self) -> None:
        # Store format: {'key': {'value': ..., 'expiry': timestamp or inf}}
        self.store: dict[str, dict[str, Any]] = {}
        # Simple event stream for telemetry
        self.event_stream: list[str] = []

    def set(self, key: str, value: str, ex: int) -> None:
        self.store[key] = {"value": value, "expiry": time.time() + ex}

    def get(self, key: str) -> str | None:
        item = self.store.get(key)
        if item:
            if time.time() < item["expiry"]:
                return item["value"]
            else:
                del self.store[key]
        return None

    def incr(self, key: str) -> int:
        current_item = self.store.get(key)
        if current_item and time.time() < current_item["expiry"]:
            try:
                current_value = int(current_item["value"])
            except Exception:
                current_value = 0
            new_value = current_value + 1
            current_item["value"] = str(new_value)
            return new_value
        else:
            new_value = 1
            self.store[key] = {"value": str(new_value), "expiry": float("inf")}
            return new_value

    def incr_with_expire(self, key: str, window: int) -> int:
        """
        Atomic-like INCR+EXPIRE semantics:
        - If key exists and not expired: increment and return new value (preserve expiry).
        - If key missing or expired: create with value=1 and expiry=now+window.
        """
        current_item = self.store.get(key)
        if current_item and time.time() < current_item["expiry"]:
            try:
                current_value = int(current_item["value"])
            except Exception:
                current_value = 0
            new_value = current_value + 1
            current_item["value"] = str(new_value)
            return new_value
        else:
            new_value = 1
            self.store[key] = {"value": str(new_value), "expiry": time.time() + window}
            return new_value

    def expire(self, key: str, ex: int) -> bool:
        item = self.store.get(key)
        if item:
            item["expiry"] = time.time() + ex
            return True
        return False

    def lpush(self, key: str, value: str) -> None:
        if key == "telemetry_stream":
            self.event_stream.insert(0, value)
            if len(self.event_stream) > 100:
                self.event_stream.pop()

    def lrange(self, key: str, start: int, stop: int) -> list[bytes]:
        if key == "identity_events_stream":
            # return bytes to mirror redis-py behavior for consumers that decode
            return [
                e.encode("utf-8") if isinstance(e, str) else e
                for e in self.event_stream[start : stop + 1]
            ]
        return []

    def ping(self) -> bool:
        return True


class MockDBClient:
    def check_connection(self) -> bool:
        return True


class MockDBUser:
    def __init__(self, username: str, password_hash: str) -> None:
        self.id: str = f"user-{username}"
        self.username: str = username
        self.is_active: bool = True


def mock_db_lookup_user(username: str) -> MockDBUser | None:
    MOCK_USERS: dict[str, MockDBUser] = {
        "probe-user": MockDBUser("probe-user", "hashed_password_abc"),
        "test-user": MockDBUser("test-user", "another_hash_xyz"),
    }
    return MOCK_USERS.get(username)


def get_redis_client() -> MockRedisClient:
    if not hasattr(get_redis_client, "client"):
        get_redis_client.client = MockRedisClient()
    return get_redis_client.client


def get_db_client() -> MockDBClient:
    if not hasattr(get_db_client, "client"):
        get_db_client.client = MockDBClient()
    return get_db_client.client


# =========================================================================
# --- TELEMETRY SCHEMA STANDARDIZATION ---
# =========================================================================


def log_standard_event(
    actor_id: str,
    event_type: str,
    ip: str = "0.0.0.0",
    user_agent: str = "Synthetic Probe",
    details: dict[str, Any] | None = None,
) -> None:
    """
    Log an event with a consistent schema into the telemetry stream (mock Redis).
    """
    client = get_redis_client()
    if not client:
        logger.warning("Redis client unavailable. Telemetry event dropped.")
        return

    event: dict[str, Any] = {
        "timestamp": int(time.time()),
        "actor_id": actor_id,
        "event_type": event_type,
        "ip": ip,
        "user_agent": user_agent,
        "details": details or {},
    }

    try:
        client.lpush("telemetry_stream", json.dumps(event))
    except Exception as e:
        logger.exception("Failed to log telemetry event: %s", e)


# =========================================================================
# --- SYNTHETIC HEALTH PROBE ---
# =========================================================================


def mock_jwt_generate(user: MockDBUser) -> str:
    jti_refresh = f"jtr-{user.id}-{int(time.time())}"
    get_redis_client().set(f"session:{jti_refresh}", "active", ex=3600 * 24 * 30)
    return f"mock_access_token_for_{user.id}"


def synthetic_login_probe(username: str = "probe-user") -> dict[str, Any]:
    start_time = time.time()
    # Explicitly typed containers so mypy knows we can index into them
    steps: dict[str, str] = {}
    results: dict[str, Any] = {"success": False, "duration_ms": 0.0, "steps": steps}

    # infrastructure checks
    redis_client = get_redis_client()
    db_client = get_db_client()

    try:
        steps["redis_ping"] = "PASS" if redis_client.ping() else "FAIL"
        steps["db_query"] = "PASS" if db_client.check_connection() else "FAIL"
        if steps["redis_ping"] == "FAIL" or steps["db_query"] == "FAIL":
            raise Exception("Infrastructure check failed.")
    except Exception as e:
        steps["infrastructure_check"] = f"FAIL: {e}"
        results["duration_ms"] = (time.time() - start_time) * 1000
        return results

    try:
        user = mock_db_lookup_user(username)
        if not user or not user.is_active:
            steps["user_lookup"] = "FAIL: User inactive or not found"
            raise Exception("User lookup failed")
        steps["user_lookup"] = "PASS"

        # typed `steps` makes these indexed assignments acceptable to mypy
        steps["password_validate"] = "PASS (Mocked)"
        mock_jwt_generate(user)
        steps["jwt_generation"] = "PASS"

        log_standard_event(
            actor_id=user.id,
            event_type="synthetic_login_success",
            ip="127.0.0.1",
            user_agent="HealthCheck/SyntheticProbe",
            details={"login_type": "synthetic"},
        )
        steps["telemetry_logged"] = "PASS"
        results["success"] = True

    except Exception as e:
        results["success"] = False
        results["error"] = f"Probe failed during auth pipeline: {e}"
        steps["final_status"] = "FAIL"

    results["duration_ms"] = (time.time() - start_time) * 1000
    return results


# =========================================================================
# --- JWT REVOCATION SERVICE ---
# =========================================================================

BLACKLIST_PREFIX = "jwt_blacklist:"


def add_token_to_blacklist(jti: str, exp: int) -> bool:
    client = get_redis_client()
    if not client:
        logger.error("Redis client unavailable. Cannot blacklist token.")
        return False
    now = int(time.time())
    remaining_lifetime = max(0, exp - now)
    redis_key = f"{BLACKLIST_PREFIX}{jti}"
    client.set(redis_key, "revoked", ex=remaining_lifetime)
    return True


def is_token_blacklisted(jti: str) -> bool:
    client = get_redis_client()
    if not client:
        logger.warning("Redis client unavailable. Assuming token is NOT blacklisted.")
        return False
    redis_key = f"{BLACKLIST_PREFIX}{jti}"
    return client.get(redis_key) is not None


def token_revoked_check(jwt_header: dict[str, Any], jwt_payload: dict[str, Any]) -> bool:
    jti = jwt_payload.get("jti")
    if not jti:
        return True
    return is_token_blacklisted(cast(str, jti))


# =========================================================================
# --- DEMONSTRATION / LOCAL TESTS (run as script) ---
# =========================================================================

if __name__ == "__main__":
    print("--- 1. Synthetic Health Probe Test ---")
    probe_results = synthetic_login_probe()
    result_label = "SUCCESS" if probe_results["success"] else "FAILURE"
    print(f"Result: {result_label} (Duration: {probe_results['duration_ms']:.2f}ms)")
    print("Steps Breakdown:")
    for step, status in probe_results["steps"].items():
        print(f"  - {step}: {status}")

    print("\n--- 2. Telemetry Schema Test ---")
    log_standard_event(
        actor_id="user-456",
        event_type="password_reset_initiated",
        ip="203.0.113.42",
        user_agent="Chrome/120.0",
        details={"method": "email", "link_expiry_s": 3600},
    )
    mock_redis = get_redis_client()
    stream_data = mock_redis.event_stream
    print(f"\n--- Recent Telemetry Events ({len(stream_data)} total) ---")
    for i, event_str in enumerate(stream_data):
        event = json.loads(event_str)
        print(
            f"Event {i+1}: Type={event['event_type']}, Actor={event['actor_id']}, IP={event['ip']}"
        )

    print("\n--- 3. JWT Revocation Test ---")
    mock_token_claims: dict[str, Any] = {
        "jti": "abc-123-refresh-token",
        "exp": int(time.time()) + 60,
        "type": "refresh",
    }
    print(f"Initial Check: Revoked={token_revoked_check({}, mock_token_claims)}")
    # Convert/cast to the expected types before passing to add_token_to_blacklist
    jti_val = str(mock_token_claims["jti"])
    exp_val = int(mock_token_claims["exp"])
    add_token_to_blacklist(jti=jti_val, exp=exp_val)
    print(f"Post-Revocation Check: Revoked={token_revoked_check({}, mock_token_claims)}")

    print("\n--- 4. MFA Rate Limit Test ---")
    test_user = "user-101"
    test_ip = "192.168.1.1"
    for i in range(1, 4):
        # Note: The test uses string arguments, which works with the Optional signatures
        if check_mfa_send_rate_limit(test_user, test_ip):
            print(f"MFA Send {i}: ALLOWED")
            record_mfa_send_request(test_user, test_ip)
        else:
            print(f"MFA Send {i}: BLOCKED (ERROR)")
    if check_mfa_send_rate_limit(test_user, test_ip):
        print("MFA Send 4: FAILED (Should have been blocked!)")
    else:
        print("MFA Send 4: BLOCKED (SUCCESS)")
