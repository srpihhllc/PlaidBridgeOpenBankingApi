# =============================================================================
# FILE: app/security_utilities.py
# DESCRIPTION: Core operational security utilities, fallback authorization vectors,
#              and isolated synthetic health probe monitoring infrastructure.
# =============================================================================

from __future__ import annotations

import importlib
import json
import logging
import time
from typing import Any, Callable, cast

logger = logging.getLogger(__name__)

# System execution limits for default MFA token rate-limiting shims.
MFA_LIMIT_WINDOW_SECONDS: int = 60
MFA_REQUEST_LIMIT: int = 3


def _resolve_production_mfa_helpers() -> tuple[
    Callable[..., Any] | None,
    Callable[..., Any] | None,
]:
    """Resolve production MFA helpers without rebinding import names."""
    module_names = (
        "app.security.mfa_helpers",
        "app.services.mfa_helpers",
        "app.services.security_helpers",
    )

    for module_name in module_names:
        try:
            module = importlib.import_module(module_name)
            check_helper = getattr(module, "check_mfa_send_rate_limit")
            record_helper = getattr(module, "record_mfa_send_request")
        except (ImportError, AttributeError):
            continue

        if callable(check_helper) and callable(record_helper):
            return check_helper, record_helper

    logger.warning(
        "Production MFA services unresolvable. "
        "Engaging localized mock rate-limiting engines."
    )
    return None, None


_ProductionCheckMFA, _ProductionRecordMFA = _resolve_production_mfa_helpers()


def check_mfa_send_rate_limit(
    user_id: str | None,
    ip_address: str | None = None,
) -> bool:
    """
    Evaluate transmission limits using the local mock Redis client.

    Returns True when allowed and False when blocked. Fails open if the cache
    is unavailable or a counter cannot be parsed.
    """
    client = get_redis_client()
    if not client:
        logger.debug(
            "MFA rate-limit skip for user=%s ip=%s (cache unavailable).",
            user_id,
            ip_address,
        )
        return True

    try:
        if user_id:
            user_key = f"rate:mfa_send:user:{user_id}"
            user_count_str = client.get(user_key)
            user_count = int(user_count_str) if user_count_str else 0
            if user_count >= MFA_REQUEST_LIMIT:
                logger.warning(
                    "MFA rate limit exhausted for user ID %s (count: %d)",
                    user_id,
                    user_count,
                )
                return False

        if ip_address:
            ip_key = f"rate:mfa_send:ip:{ip_address}"
            ip_count_str = client.get(ip_key)
            ip_count = int(ip_count_str) if ip_count_str else 0
            if ip_count >= MFA_REQUEST_LIMIT:
                logger.warning(
                    "MFA rate limit exhausted for origin IP %s (count: %d)",
                    ip_address,
                    ip_count,
                )
                return False

        return True

    except (TypeError, ValueError):
        logger.exception(
            "Malformed MFA rate-limit counter. Failing open for user=%s ip=%s",
            user_id,
            ip_address,
        )
        return True


def record_mfa_send_request(
    user_id: str | None,
    ip_address: str | None = None,
    channel: str = "sms",
    masked_dest: str | None = None,
) -> None:
    """Record an MFA transmission against the local mock Redis client."""
    client = get_redis_client()
    if not client:
        logger.debug(
            "MFA tracking dropped for user=%s ip=%s channel=%s (cache unavailable).",
            user_id,
            ip_address,
            channel,
        )
        return

    window = MFA_LIMIT_WINDOW_SECONDS

    if user_id:
        client.incr_with_expire(f"rate:mfa_send:user:{user_id}", window)

    if ip_address:
        client.incr_with_expire(f"rate:mfa_send:ip:{ip_address}", window)

    logger.debug(
        "MFA request recorded for user=%s ip=%s channel=%s destination=%s",
        user_id,
        ip_address,
        channel,
        masked_dest,
    )


# =============================================================================
# MOCK CONTAINERS: TELEMETRY, DATA STRUCTURES, AND INFRASTRUCTURE
# =============================================================================


class MockRedisClient:
    """In-memory mock Redis client with expirations and telemetry buffering."""

    def __init__(self) -> None:
        self.store: dict[str, dict[str, Any]] = {}
        self.event_stream: list[str] = []

    def set(self, key: str, value: str, ex: int) -> None:
        self.store[key] = {"value": value, "expiry": time.time() + ex}

    def get(self, key: str) -> str | None:
        item = self.store.get(key)
        if item:
            if time.time() < item["expiry"]:
                return str(item["value"])
            del self.store[key]
        return None

    def incr(self, key: str) -> int:
        current_item = self.store.get(key)
        if current_item and time.time() < current_item["expiry"]:
            try:
                current_value = int(current_item["value"])
            except (ValueError, TypeError):
                current_value = 0

            new_value = current_value + 1
            current_item["value"] = str(new_value)
            return new_value

        new_value = 1
        self.store[key] = {"value": str(new_value), "expiry": float("inf")}
        return new_value

    def incr_with_expire(self, key: str, window: int) -> int:
        """Increment a counter, setting its expiry when the key is first created."""
        current_item = self.store.get(key)
        if current_item and time.time() < current_item["expiry"]:
            try:
                current_value = int(current_item["value"])
            except (ValueError, TypeError):
                current_value = 0

            new_value = current_value + 1
            current_item["value"] = str(new_value)
            return new_value

        new_value = 1
        self.store[key] = {
            "value": str(new_value),
            "expiry": time.time() + window,
        }
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
        if key in {"identity_events_stream", "telemetry_stream"}:
            return [
                element.encode("utf-8")
                if isinstance(element, str)
                else element
                for element in self.event_stream[start : stop + 1]
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
    mock_identity_pool: dict[str, MockDBUser] = {
        "probe-user": MockDBUser("probe-user", "hashed_password_abc"),
        "test-user": MockDBUser("test-user", "another_hash_xyz"),
    }
    return mock_identity_pool.get(username)


def get_redis_client() -> MockRedisClient:
    """Get or create the process-local mock Redis client."""
    if not hasattr(get_redis_client, "client"):
        setattr(get_redis_client, "client", MockRedisClient())
    return cast(MockRedisClient, getattr(get_redis_client, "client"))


def get_db_client() -> MockDBClient:
    """Get or create the process-local mock database client."""
    if not hasattr(get_db_client, "client"):
        setattr(get_db_client, "client", MockDBClient())
    return cast(MockDBClient, getattr(get_db_client, "client"))


# =============================================================================
# TELEMETRY ENGINE
# =============================================================================


def log_standard_event(
    actor_id: str,
    event_type: str,
    ip: str = "127.0.0.1",
    user_agent: str = "Synthetic Probe",
    details: dict[str, Any] | None = None,
) -> None:
    """Serialize and queue an audit event in the local telemetry stream."""
    client = get_redis_client()
    if not client:
        logger.warning(
            "Metrics infrastructure unavailable. Dropping structural event log."
        )
        return

    event_payload: dict[str, Any] = {
        "timestamp": int(time.time()),
        "actor_id": actor_id,
        "event_type": event_type,
        "ip": ip,
        "user_agent": user_agent,
        "details": details or {},
    }

    try:
        client.lpush("telemetry_stream", json.dumps(event_payload))
    except Exception:
        logger.exception(
            "Telemetry pipeline failure while tracking actor event %s",
            actor_id,
        )


# =============================================================================
# SYNTHETIC SUBSYSTEM HEALTH PROBE
# =============================================================================


def mock_jwt_generate(user: MockDBUser) -> str:
    jti_refresh = f"jtr-{user.id}-{int(time.time())}"
    get_redis_client().set(f"session:{jti_refresh}", "active", ex=86400)
    return f"mock_access_token_for_{user.id}"


def synthetic_login_probe(username: str = "probe-user") -> dict[str, Any]:
    """Run a synthetic identity diagnostic against the mock infrastructure."""
    start_execution_time = time.time()
    diagnostic_steps: dict[str, str] = {}
    probe_response: dict[str, Any] = {
        "success": False,
        "duration_ms": 0.0,
        "steps": diagnostic_steps,
    }

    redis_cluster = get_redis_client()
    database_node = get_db_client()

    try:
        diagnostic_steps["redis_ping"] = (
            "PASS" if redis_cluster.ping() else "FAIL"
        )
        diagnostic_steps["db_query"] = (
            "PASS" if database_node.check_connection() else "FAIL"
        )
        if "FAIL" in diagnostic_steps.values():
            raise RuntimeError(
                "Infrastructure nodes faulted during the initial probe."
            )
    except Exception as exc:
        diagnostic_steps["infrastructure_check"] = f"FAIL: {exc}"
        probe_response["duration_ms"] = (
            time.time() - start_execution_time
        ) * 1000
        return probe_response

    try:
        user_record = mock_db_lookup_user(username)
        if not user_record or not user_record.is_active:
            diagnostic_steps["user_lookup"] = (
                "FAIL: Target account missing or disabled."
            )
            raise ValueError("Identity authentication boundaries unverified.")

        diagnostic_steps["user_lookup"] = "PASS"
        diagnostic_steps["password_validate"] = "PASS (Mocked)"

        mock_jwt_generate(user_record)
        diagnostic_steps["jwt_generation"] = "PASS"

        log_standard_event(
            actor_id=user_record.id,
            event_type="synthetic_login_success",
            ip="127.0.0.1",
            user_agent="HealthCheck/SyntheticProbe",
            details={"login_type": "synthetic"},
        )
        diagnostic_steps["telemetry_logged"] = "PASS"
        probe_response["success"] = True

    except Exception as exc:
        probe_response["success"] = False
        probe_response["error"] = (
            f"Authentication pipeline error: {exc}"
        )
        diagnostic_steps["final_status"] = "FAIL"

    probe_response["duration_ms"] = (
        time.time() - start_execution_time
    ) * 1000
    return probe_response


# =============================================================================
# STATE CONSTRAINTS / ACCESS TOKEN REVOCATION SERVICES
# =============================================================================

BLACKLIST_PREFIX: str = "jwt_blacklist:"


def add_token_to_blacklist(jti: str, exp: int) -> bool:
    """Add a JWT identifier to the revocation index."""
    client = get_redis_client()
    if not client:
        logger.error("Cache infrastructure unavailable; blacklist write abandoned.")
        return False

    ttl_duration = max(0, exp - int(time.time()))
    client.set(f"{BLACKLIST_PREFIX}{jti}", "revoked", ex=ttl_duration)
    return True


def is_token_blacklisted(jti: str) -> bool:
    """Check whether a token identifier is present in the revocation index."""
    client = get_redis_client()
    if not client:
        logger.warning("Cache unavailable; skipping blacklist lookup.")
        return False

    return client.get(f"{BLACKLIST_PREFIX}{jti}") is not None


def token_revoked_check(
    jwt_header: dict[str, Any],
    jwt_payload: dict[str, Any],
) -> bool:
    """Callback used by authorization engines to check token revocation."""
    token_identifier = jwt_payload.get("jti")
    if not token_identifier:
        return True
    return is_token_blacklisted(cast(str, token_identifier))


# =============================================================================
# FUNCTIONAL VERIFICATION
# =============================================================================

if __name__ == "__main__":
    print("--- 1. Synthetic infrastructure health probe ---")
    results = synthetic_login_probe()
    status_flag = "SUCCESS" if results["success"] else "FAILURE"
    print(
        f"Probe resolution: {status_flag} "
        f"(latency: {results['duration_ms']:.3f}ms)"
    )
    print("Pipeline trace:")
    for step_key, step_status in results["steps"].items():
        print(f"  {step_key}: {step_status}")

    print("\n--- 2. Telemetry schema test ---")
    log_standard_event(
        actor_id="user-456",
        event_type="password_reset_initiated",
        ip="203.0.113.42",
        user_agent="Mozilla/Chrome/120.0",
        details={"method": "email", "link_expiry_s": 3600},
    )

    mock_redis = get_redis_client()
    event_stream_output = mock_redis.lrange("telemetry_stream", 0, 10)
    print(f"Captured telemetry records: {len(event_stream_output)}")
    for index, raw_bytes in enumerate(event_stream_output):
        parsed_record = json.loads(raw_bytes.decode("utf-8"))
        print(
            f"  Record [{index + 1}]: "
            f"Type={parsed_record['event_type']} | "
            f"Actor={parsed_record['actor_id']} | "
            f"Source={parsed_record['ip']}"
        )

    print("\n--- 3. Token blacklist test ---")
    mock_claims: dict[str, Any] = {
        "jti": "abc-123-refresh-token",
        "exp": int(time.time()) + 60,
        "type": "refresh",
    }
    print(
        "Before revocation: "
        f"revoked={token_revoked_check({}, mock_claims)}"
    )
    add_token_to_blacklist(
        jti=str(mock_claims["jti"]),
        exp=int(mock_claims["exp"]),
    )
    print(
        "After revocation: "
        f"revoked={token_revoked_check({}, mock_claims)}"
    )

    print("\n--- 4. MFA rate-limit test ---")
    identity_node = "user-101"
    network_origin = "192.168.1.1"

    for current_pass in range(1, 4):
        if check_mfa_send_rate_limit(identity_node, network_origin):
            print(f"  Transaction {current_pass}: PERMITTED")
            record_mfa_send_request(identity_node, network_origin)
        else:
            print(f"  Transaction {current_pass}: DENIED")

    if check_mfa_send_rate_limit(identity_node, network_origin):
        print("  Transaction 4: EXHAUSTION CONTROL FAILURE")
    else:
        print("  Transaction 4: DENIED (expected)")