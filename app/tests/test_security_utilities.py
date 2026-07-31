# =============================================================================
# FILE: app/tests/test_security_utilities.py
# DESCRIPTION: Deep isolation coverage matrix for app/security_utilities.py
# =============================================================================

import json
import time
from unittest.mock import patch, MagicMock
import pytest

from app.security_utilities import (
    get_redis_client,
    get_db_client,
    check_mfa_send_rate_limit,
    record_mfa_send_request,
    MockRedisClient,
    MockDBClient,
    MockDBUser,
    mock_db_lookup_user,
    log_standard_event,
    synthetic_login_probe,
    add_token_to_blacklist,
    is_token_blacklisted,
    token_revoked_check,
    mock_jwt_generate,
    MFA_REQUEST_LIMIT
)


@pytest.fixture(autouse=True)
def clean_infrastructure_state():
    """Ensures cached helper states and singleton attributes are fresh for every run."""
    if hasattr(get_redis_client, "client"):
        delattr(get_redis_client, "client")
    if hasattr(get_db_client, "client"):
        delattr(get_db_client, "client")
    yield
    if hasattr(get_redis_client, "client"):
        delattr(get_redis_client, "client")
    if hasattr(get_db_client, "client"):
        delattr(get_db_client, "client")


# =============================================================================
# 1. FALLBACK MFA RATE LIMITER SECTOR
# =============================================================================

def test_mfa_rate_limit_fail_open_when_redis_unavailable():
    """Should fail-open safely (returning True) if the mock Redis engine is absent."""
    with patch("app.security_utilities.get_redis_client", return_value=None):
        assert check_mfa_send_rate_limit(user_id="user-123", ip_address="127.0.0.1") is True
        # Ensure recorder handles a missing client context gracefully without throwing an exception
        record_mfa_send_request(user_id="user-123", ip_address="127.0.0.1")


def test_mfa_rate_limit_user_saturation():
    """Should block request verification if user_id count hits or exceeds the limit threshold."""
    client = get_redis_client()
    user_id = "target-subscriber"
    user_key = f"rate:mfa_send:user:{user_id}"
    
    # Inject limit saturation directly into store
    client.set(user_key, str(MFA_REQUEST_LIMIT), ex=60)
    assert check_mfa_send_rate_limit(user_id=user_id, ip_address=None) is False


def test_mfa_rate_limit_ip_saturation():
    """Should block request verification if ip_address count hits or exceeds the limit threshold."""
    client = get_redis_client()
    ip_addr = "192.168.1.50"
    ip_key = f"rate:mfa_send:ip:{ip_addr}"
    
    client.set(ip_key, str(MFA_REQUEST_LIMIT), ex=60)
    assert check_mfa_send_rate_limit(user_id=None, ip_address=ip_addr) is False


def test_mfa_rate_limit_recording_increments_both_tracks():
    """Should accurately advance both the user and the IP atomic increment windows."""
    user_id = "user-alpha"
    ip_addr = "10.0.0.5"
    
    record_mfa_send_request(user_id=user_id, ip_address=ip_addr)
    client = get_redis_client()
    
    assert client.get(f"rate:mfa_send:user:{user_id}") == "1"
    assert client.get(f"rate:mfa_send:ip:{ip_addr}") == "1"


# =============================================================================
# 2. MOCK REDIS CLIENT CORNER CASES
# =============================================================================

def test_mock_redis_get_with_expired_key_purges_storage():
    """Reading an expired key must drop it from the inner storage topology and return None."""
    client = MockRedisClient()
    client.store["expired_token"] = {"value": "revoked", "expiry": time.time() - 10}
    
    assert client.get("expired_token") is None
    assert "expired_token" not in client.store


def test_mock_redis_incr_resilient_to_malformed_integer_strings():
    """Incr should fall back to base initialization if value parsing throws ValueError."""
    client = MockRedisClient()
    client.store["bad_int"] = {"value": "corrupted_payload", "expiry": time.time() + 10}
    
    assert client.incr("bad_int") == 1


def test_mock_redis_incr_on_expired_key_resets_lifecycle():
    """Incr on an expired entry should overwrite it with a fresh initialization state."""
    client = MockRedisClient()
    client.store["stale_counter"] = {"value": "58", "expiry": time.time() - 5}
    
    assert client.incr("stale_counter") == 1


def test_mock_redis_incr_with_expire_resilient_to_malformed_strings():
    """Incr_with_expire should handle structural ValueError and default initialization seamlessly."""
    client = MockRedisClient()
    client.store["bad_int_expire"] = {"value": "malformed", "expiry": time.time() + 10}
    
    assert client.incr_with_expire("bad_int_expire", window=60) == 1


def test_mock_redis_expire_mapping_returns_accurate_status():
    """Expire must return True if item is mapped, and False if target missing."""
    client = MockRedisClient()
    assert client.expire("nonexistent_key", ex=30) is False
    
    client.set("active_key", "payload", ex=10)
    assert client.expire("active_key", ex=45) is True


def test_mock_redis_telemetry_stream_buffer_eviction():
    """Pushing past 100 entries on telemetry_stream should cap the buffer size to prevent memory leaks."""
    client = MockRedisClient()
    for i in range(105):
        client.lpush("telemetry_stream", f"frame_{i}")
        
    assert len(client.event_stream) == 100


def test_mock_redis_lrange_encodes_to_bytes():
    """Lrange on identity_events_stream must match standard redis-py byte casting behaviors."""
    client = MockRedisClient()
    client.event_stream = ["event_block_A", "event_block_B"]
    
    payload = client.lrange("identity_events_stream", start=0, stop=1)
    assert payload == [b"event_block_A", b"event_block_B"]
    
    # Assert alternate keys return unmapped blank lists
    assert client.lrange("unsupported_stream_key", start=0, stop=1) == []


# =============================================================================
# 3. TELEMETRY FRAMEWORK & DATABASE SEED CHECKERS
# =============================================================================

def test_log_standard_event_handles_redis_disconnect_gracefully():
    """Telemetry logging should drop frames safely if the backend goes offline."""
    with patch("app.security_utilities.get_redis_client", return_value=None):
        # Should execute without throwing or stalling
        log_standard_event(actor_id="user-1", event_type="test_drop")


def test_log_standard_event_handles_serialization_exceptions(caplog):
    """Should catch exceptions thrown during lpush operations and log them."""
    with patch("app.security_utilities.get_redis_client") as mock_get:
        mock_client = MagicMock()
        mock_client.lpush.side_effect = Exception("Atomic streaming write crash")
        mock_get.return_value = mock_client
        
        log_standard_event(actor_id="actor-99", event_type="critical_sys")
        
        # Matches the precision tracking message signature recorded to stderr/logs
        assert any("Structural telemetry pipeline failure" in record.message for record in caplog.records)


def test_mock_db_lookup_user_matrix():
    """Assert domain user seeding handles canonical entries and missed queries cleanly."""
    assert mock_db_lookup_user("probe-user") is not None
    assert mock_db_lookup_user("test-user") is not None
    assert mock_db_lookup_user("malicious-actor") is None


# =============================================================================
# 4. SYNTHETIC HEALTH PROBE SECTOR
# =============================================================================

def test_synthetic_login_probe_success_path():
    """The automated health probe loop should run completely green on valid baseline environments."""
    results = synthetic_login_probe(username="probe-user")
    assert results["success"] is True
    assert results["steps"]["redis_ping"] == "PASS"
    assert results["steps"]["db_query"] == "PASS"
    assert results["steps"]["jwt_generation"] == "PASS"


def test_synthetic_login_probe_infrastructure_isolation_failure():
    """The probe should fail fast and log early if a database or cache check fails."""
    with patch.object(MockRedisClient, "ping", return_value=False):
        results = synthetic_login_probe(username="probe-user")
        assert results["success"] is False
        assert "FAIL" in results["steps"]["infrastructure_check"]


def test_synthetic_login_probe_missing_or_suspended_user():
    """The probe should accurately log a failure step if the lookups target an unseeded account."""
    results = synthetic_login_probe(username="unknown-account")
    assert results["success"] is False
    # Verified against the specific string produced by the security mapping layer
    assert "Identity authentication boundaries unverified" in results["error"]


def test_synthetic_login_probe_inactive_user_handling():
    """The probe should intercept the validation layer if the seeded user record is marked inactive."""
    with patch("app.security_utilities.mock_db_lookup_user") as mock_lookup:
        suspended_user = MockDBUser("probe-user", "hash")
        suspended_user.is_active = False
        mock_lookup.return_value = suspended_user
        
        results = synthetic_login_probe(username="probe-user")
        assert results["success"] is False


# =============================================================================
# 5. JWT REVOCATION LIFECYCLE SERVICE
# =============================================================================

def test_jwt_revocation_service_handles_offline_cache():
    """Blacklist operations must drop cleanly and flag False if the cache context drops offline."""
    with patch("app.security_utilities.get_redis_client", return_value=None):
        assert add_token_to_blacklist(jti="jti-123", exp=int(time.time()) + 100) is False
        assert is_token_blacklisted(jti="jti-123") is False


def test_token_revoked_check_interprets_missing_jti_as_revoked():
    """Security Boundary Check: Payloads completely missing a JTI identifier claim must be flagged as revoked."""
    # Returns True to guarantee fail-closed enforcement on malformed claims tokens
    assert token_revoked_check(jwt_header={}, jwt_payload={"sub": "user-1"}) is True


def test_token_revoked_check_valid_vs_invalid_lifecycle():
    """Verify state transitions of claims tokens through active blacklist tracking."""
    claims = {"jti": "refresh-token-uuid", "exp": int(time.time()) + 300}
    
    # Initially clear
    assert token_revoked_check(jwt_header={}, jwt_payload=claims) is False
    
    # Process revocation
    add_token_to_blacklist(jti=claims["jti"], exp=claims["exp"])
    
    # Must now capture as blacklisted
    assert token_revoked_check(jwt_header={}, jwt_payload=claims) is True