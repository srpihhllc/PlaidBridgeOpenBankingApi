# =============================================================================
# FILE: app/tests/test_latency_trace.py
# DESCRIPTION: Unit tests for emit_latency_trace covering all supported call signatures,
#              TTL consistency, fallback behavior, trace delegation, performance,
#              concurrency, and property-based testing.
# =============================================================================

# ==============================================================================
# TEST SUITE: Latency Trace & TTL Telemetry (Moved to unit/ directory)
#
# CI/Coverage Configuration Notes:
#
# 1. CI Markers:
#    - @pytest.mark.ci: For fast, core unit tests (run on every commit).
#    - @pytest.mark.nightly: For slow, long-running, or stress/fuzzing tests.
#
# 2. Coverage Hook:
#    Coverage is now wired automatically via pyproject.toml's addopts.
#
# ==============================================================================

import datetime
import logging
import os  # NEW: Added for environment variable check in soak test
import re  # Added for pattern matching in value assertions
import threading  # Added for concurrency testing
import time
import uuid  # Added for generating unique IDs in concurrent tests

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st  # Added for property-based testing

# NOTE: The provided test file imports from app.telemetry.ttl_emit
from app.telemetry.ttl_emit import _ttl_data, emit_boot_trace, ttl_summary
from app.utils.latency import emit_latency_trace

# Set up logging for better visibility during complex tests
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


@pytest.fixture(autouse=True)
def clear_ttl_data():
    """
    Clears and restores the global _ttl_data state before and after each test
    to ensure test isolation, especially for tests interacting with ttl_summary.
    """
    # Import inside the fixture to ensure access to the global variable
    from app.telemetry.ttl_emit import _ttl_data

    # Use a lock for thread safety when manipulating global state
    lock = threading.Lock()
    with lock:
        snapshot = dict(_ttl_data)
        _ttl_data.clear()
    yield
    with lock:
        _ttl_data.clear()
        _ttl_data.update(snapshot)


@pytest.fixture
def capture_ttl_emit(monkeypatch):
    """
    Monkeypatches ttl_emit to capture all calls for inspection.
    Returns a thread-safe list of (args, kwargs) tuples.
    """
    calls = []
    lock = threading.Lock()  # Make captures thread-safe

    def fake_ttl_emit(*args, **kwargs):
        with lock:
            calls.append((args, kwargs))

    # Assuming the actual implementation of ttl_emit is in app.telemetry.ttl_emit
    # Adjust path if ttl_emit is imported differently by emit_latency_trace
    monkeypatch.setattr("app.utils.latency.ttl_emit", fake_ttl_emit)
    return calls


# === Signature Coverage ===
@pytest.mark.ci
def test_new_signature_positional(capture_ttl_emit):
    """New-style positional: emit_latency_trace(stage, request_uuid, start_ts, r)."""
    start_time = time.time() - 0.1  # Simulate 100ms latency
    emit_latency_trace("auth", "req-123", start_time, r="fake")
    args, kwargs = capture_ttl_emit[0]

    # Key and TTL assertion
    key_found = any(
        "ttl:flow:oauth:google:auth:latency:req-123" in str(v)
        for v in args + tuple(kwargs.values())
    )
    assert key_found
    assert kwargs.get("ttl") == 300

    # Value assertion: should be in format "latency_ms:{int}"
    # The value is passed as a keyword argument 'value' after processing
    value_payload = kwargs.get("value", "")
    # Use anchored regex to ensure the entire string matches the format
    assert re.match(r"^latency_ms:\d+$", value_payload)


@pytest.mark.ci
def test_legacy_signature_positional(capture_ttl_emit):
    """Legacy-style positional: emit_latency_trace(endpoint, latency_ms, r)."""
    emit_latency_trace("user_login", 123.45, r="fake")
    args, kwargs = capture_ttl_emit[0]

    # Key and TTL assertion
    key_found = any("latency:user_login" in str(v) for v in args + tuple(kwargs.values()))
    assert key_found
    assert kwargs.get("ttl") == 300  # Should be 300 after unification

    # Value assertion: should be the string representation of the float, using kwargs
    # for consistency
    value_payload = kwargs.get("value")
    # Explicit type check
    assert isinstance(value_payload, str)
    assert value_payload == "123.45"


@pytest.mark.ci
def test_new_signature_keyword(capture_ttl_emit):
    """New-style keyword: emit_latency_trace(stage=..., request_uuid=..., start_ts=..., r=...)."""
    start_time = time.time() - 0.2
    emit_latency_trace(stage="token", request_uuid="abc", start_ts=start_time, r="fake")
    args, kwargs = capture_ttl_emit[0]

    # Key and TTL assertion
    key_found = any(
        "ttl:flow:oauth:google:token:latency:abc" in str(v) for v in args + tuple(kwargs.values())
    )
    assert key_found
    assert kwargs.get("ttl") == 300

    # Value assertion: should be in format "latency_ms:{int}" and is passed via kwargs
    # Use anchored regex
    assert re.match(r"^latency_ms:\d+$", kwargs.get("value", ""))


@pytest.mark.ci
def test_legacy_signature_keyword(capture_ttl_emit):
    """Legacy-style keyword: emit_latency_trace(endpoint=..., latency_ms=..., r=...)."""
    emit_latency_trace(endpoint="refresh", latency_ms=456.78, r="fake")
    args, kwargs = capture_ttl_emit[0]

    # Key and TTL assertion
    key_found = any("latency:refresh" in str(v) for v in args + tuple(kwargs.values()))
    assert key_found
    assert kwargs.get("ttl") == 300  # Should be 300 after unification

    # Value assertion: should be the string representation of the float
    value_payload = next((v for v in args if v == "456.78"), kwargs.get("value"))
    # Explicit type check
    assert isinstance(value_payload, str)
    assert value_payload == "456.78"


# === TTL Behavior ===
@pytest.mark.ci
def test_custom_ttl_override(capture_ttl_emit):
    """Custom TTL override should be respected."""
    emit_latency_trace("auth", "req-123", time.time(), r="fake", ttl_seconds=120)
    _, kwargs = capture_ttl_emit[0]
    assert kwargs.get("ttl") == 120


@pytest.mark.ci
def test_multiple_emits(capture_ttl_emit):
    """Multiple calls should result in multiple ttl_emit invocations and unique keys."""
    emit_latency_trace("auth", "req-1", time.time(), r="fake")
    emit_latency_trace("auth", "req-2", time.time(), r="fake")
    assert len(capture_ttl_emit) == 2

    # Assert keys differ to ensure trace separation and correct naming.
    keys = [kw["key"] for _, kw in capture_ttl_emit]
    assert keys == [
        "ttl:flow:oauth:google:auth:latency:req-1",
        "ttl:flow:oauth:google:auth:latency:req-2",
    ]


@pytest.mark.ci
def test_negative_duration_fallback(capture_ttl_emit):
    """Future start_ts should fallback to latency_ms:0."""
    emit_latency_trace("auth", "req-xyz", time.time() + 100, r="fake")
    _, kwargs = capture_ttl_emit[0]

    value_payload = next((v for v in kwargs.values() if "latency_ms:" in str(v)), "")
    assert value_payload == "latency_ms:0"


# === Error Handling ===
@pytest.mark.ci
def test_invalid_arguments_raises_typeerror():
    """Unsupported argument patterns should raise TypeError."""
    with pytest.raises(TypeError):
        emit_latency_trace("only_one_argument")


@pytest.mark.ci
def test_ttl_emit_signature_mismatch(monkeypatch, caplog):
    """Broken ttl_emit signature should raise TypeError and log warning."""
    # Set level to capture warning logs
    caplog.set_level("WARNING")

    def broken_ttl_emit(*args, **kwargs):
        raise TypeError("bad signature")

    # Assuming the actual implementation of ttl_emit is in app.telemetry.ttl_emit
    # Adjust path if ttl_emit is imported differently by emit_latency_trace
    monkeypatch.setattr("app.utils.latency.ttl_emit", broken_ttl_emit)

    with pytest.raises(TypeError):
        emit_latency_trace("legacy", 123.0, r="fake")

    # Assert that the specific warning message was logged
    assert "ttl_emit signature mismatch for key=latency:legacy" in caplog.text
    assert "cannot call it reliably" in caplog.text
    assert caplog.text.count("ttl_emit signature mismatch") == 1
    # Assert the correct log level was used
    assert len(caplog.records) == 1
    assert caplog.records[0].levelname == "WARNING"


# === Trace Delegation ===
@pytest.mark.ci
def test_emit_boot_trace_delegates_to_ttl_emit(monkeypatch):
    """emit_boot_trace should delegate correctly to ttl_emit."""
    calls = []

    # Assuming the actual implementation of ttl_emit is in app.telemetry.ttl_emit
    # Adjust path if ttl_emit is imported differently by emit_boot_trace
    def fake_ttl_emit(*args, **kwargs):
        calls.append((args, kwargs))

    monkeypatch.setattr("app.telemetry.ttl_emit.ttl_emit", fake_ttl_emit)

    emit_boot_trace(key="ttl:boot:blueprint:auth:complete", status="ok", r="fake")
    _, kwargs = calls[0]
    assert kwargs["key"] == "ttl:boot:blueprint:auth:complete"
    assert kwargs["status"] == "ok"
    assert kwargs["ttl"] == 60


# === TTL Summary (Relies on autouse fixture for isolation) ===
@pytest.mark.ci
def test_ttl_summary_expiry_and_freshness():
    """ttl_summary should exclude expired keys and mark freshness correctly."""
    # The clear_ttl_data fixture ensures _ttl_data is empty before this test runs.
    now = datetime.datetime.now()

    _ttl_data["key:fresh"] = {
        "expires_at": now + datetime.timedelta(seconds=10),
        "ttl_seconds": 10,
        "value": "v1",
        "status": "ok",
        "meta": {"source": "test"},
    }

    _ttl_data["key:expired"] = {
        "expires_at": now - datetime.timedelta(seconds=301),
        "ttl_seconds": 10,
        "value": "v2",
        "status": "stale",
        "meta": {"source": "test"},
    }

    summary = ttl_summary()
    assert "key:fresh" in summary
    assert "key:expired" not in summary
    assert summary["key:fresh"]["fresh"] is True
    # Verify that meta is retained for fresh entries.
    assert summary["key:fresh"]["meta"]["source"] == "test"


# === Additional Rigor Tests (Stress Test Parameterized) ===


@pytest.mark.nightly  # Mark stress test for nightly runs
@pytest.mark.parametrize(
    ("num_emits", "perf_limit_seconds"),
    [
        (
            100,
            0.5,
        ),  # Test 1: Quick check, small batch (Still run in nightly for regression)
        (1000, 3.0),  # Test 2: Scaling check, medium batch
        (10000, 30.0),  # Test 3: Large scale check (can be tuned for environment)
    ],
)
def test_stress_emits_performance(capture_ttl_emit, num_emits, perf_limit_seconds):
    """
    Emit a configurable number of traces and check uniqueness, consistency, and performance.
    Parameterized to test different batch sizes.
    """
    logging.info(f"Starting stress test with {num_emits} emits and {perf_limit_seconds}s limit.")

    loop_start_time = time.time()
    for i in range(num_emits):
        emit_latency_trace("stress", f"req-{i}", loop_start_time - (i * 0.01), r="fake")
    loop_duration = time.time() - loop_start_time

    assert len(capture_ttl_emit) == num_emits
    # Performance assertion
    assert (
        loop_duration < perf_limit_seconds
    ), f"Stress test took too long: {loop_duration:.2f}s (Limit: {perf_limit_seconds}s)"

    keys = set()
    ttls = set()
    for _, kwargs in capture_ttl_emit:
        keys.add(kwargs.get("key"))
        ttls.add(kwargs.get("ttl"))

    assert len(keys) == num_emits  # All keys must be unique
    assert ttls == {300}  # All TTLs should be the default 300


@pytest.mark.ci
def test_boundary_ttl(capture_ttl_emit):
    """Test behavior with zero and negative TTLs."""
    # Zero TTL
    emit_latency_trace("auth", "req-zero", time.time(), r="fake", ttl_seconds=0)
    _, kwargs_zero = capture_ttl_emit[0]
    assert kwargs_zero.get("ttl") == 0

    # Negative TTL
    emit_latency_trace("auth", "req-neg", time.time(), r="fake", ttl_seconds=-10)
    _, kwargs_neg = capture_ttl_emit[1]
    # Assuming ttl_emit passes negative values through
    assert kwargs_neg.get("ttl") == -10


@pytest.mark.ci
def test_emit_boot_trace_with_meta(monkeypatch):
    """Assert that extra metadata passed to emit_boot_trace is preserved."""
    calls = []

    # Assuming the actual implementation of ttl_emit is in app.telemetry.ttl_emit
    # Adjust path if ttl_emit is imported differently by emit_boot_trace
    def fake_ttl_emit(*args, **kwargs):
        calls.append((args, kwargs))

    monkeypatch.setattr("app.telemetry.ttl_emit.ttl_emit", fake_ttl_emit)

    # Pass additional meta data
    emit_boot_trace(
        key="ttl:boot:meta_test",
        status="ok",
        r="fake",
        meta={"version": "1.2.3", "node": "worker-5"},
    )

    assert len(calls) == 1
    _, kwargs = calls[0]
    assert kwargs.get("key") == "ttl:boot:meta_test"
    assert kwargs.get("status") == "ok"
    assert kwargs.get("ttl") == 60
    # Check that the meta dictionary is present and contains the expected data
    assert "meta" in kwargs
    assert kwargs["meta"] == {"version": "1.2.3", "node": "worker-5"}


# === Concurrency Test ===
@pytest.mark.ci
def _concurrent_emit_task(thread_id, num_calls, capture_list, lock):
    """Helper function for threading test."""
    for i in range(num_calls):
        # Generate a unique ID that includes the thread ID and iteration count
        req_id = f"T{thread_id}-R{i}-{uuid.uuid4().hex[:8]}"
        start_ts = time.time() - 0.05
        emit_latency_trace(f"concurrent_stage_{thread_id}", req_id, start_ts, r="fake")
        # Note: capture_ttl_emit is thread-safe due to its internal lock


@pytest.mark.ci
def test_concurrent_emits(capture_ttl_emit):
    """Test emit_latency_trace under concurrent calls using threads."""
    num_threads = 5
    calls_per_thread = 20
    total_expected_calls = num_threads * calls_per_thread

    threads = []
    # Create a dummy lock to pass to the helper function, although the capture_ttl_emit
    # lock is sufficient
    dummy_lock = threading.Lock()
    for i in range(num_threads):
        thread = threading.Thread(
            target=_concurrent_emit_task,
            args=(i, calls_per_thread, capture_ttl_emit, dummy_lock),
        )
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join(timeout=5)  # Wait for threads to complete with a timeout

    # Check if the correct number of calls were captured (thread-safe)
    assert len(capture_ttl_emit) == total_expected_calls

    # Check if all keys generated are unique
    keys = set()
    for _, kwargs in capture_ttl_emit:
        keys.add(kwargs.get("key"))
    assert len(keys) == total_expected_calls, "Not all concurrent traces resulted in unique keys."


# === Property-Based Testing ===

# Define strategies for generating test data
# Use simple alphanumeric strings for stage/request_id to avoid complex characters
safe_text = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N")), min_size=1, max_size=20
)
# Timestamps spanning a 2-hour window, to test future/past inputs
timestamps = st.floats(min_value=time.time() - 3600, max_value=time.time() + 3600)
latencies = st.floats(min_value=0.0, max_value=10000.0)  # 0ms to 10s
ttls = st.integers(min_value=-100, max_value=3600)  # Allow negative/zero/positive TTLs


@pytest.mark.ci
@settings(
    max_examples=100, deadline=None
)  # Increased examples for better fuzzing, disable deadline
@given(
    stage=safe_text,
    request_id=st.text(
        alphabet=st.characters(whitelist_categories=("L", "N")), min_size=1, max_size=20
    ).map(lambda x: x if x else "default_id"),
    start_ts=timestamps,
    ttl=ttls,
)
def test_property_based_new_signature(capture_ttl_emit, stage, request_id, start_ts, ttl):
    """
    Property-based test for the new signature format, including latency value
    distribution tracking.
    """
    time_before_call = time.time()
    emit_latency_trace(stage, request_id, start_ts, r="fake", ttl_seconds=ttl)
    time_after_call = time.time()

    assert len(capture_ttl_emit) == 1
    _, kwargs = capture_ttl_emit[0]

    # Key and TTL Assertions
    expected_key_part = f"ttl:flow:oauth:google:{stage}:latency:{request_id}"
    assert kwargs.get("key") == expected_key_part
    assert kwargs.get("ttl") == ttl

    # Latency Distribution and Bound Assertions
    value_payload = kwargs.get("value", "")
    assert re.match(
        r"^latency_ms:\d+$", value_payload
    ), "Latency value must be in 'latency_ms:INT' format."

    latency_ms = int(value_payload.split(":")[1])

    # 1. Non-negative assertion (Hard requirement)
    assert latency_ms >= 0, "Computed latency must be non-negative."

    # 2. Reasonable Bound Assertion (Based on strategy limits)
    # Allowing a generous upper limit of 4 million ms (4000 seconds)
    assert (
        latency_ms < 4_000_000
    ), f"Computed latency {latency_ms}ms exceeded reasonable bound of 4M ms."

    # 3. Accuracy Assertion (Within tolerance)
    expected_ms_min = max(0, int((time_before_call - start_ts) * 1000))
    expected_ms_max = max(0, int((time_after_call - start_ts) * 1000))

    # If the start time is in the future, it should be exactly 0.
    if start_ts > time_before_call:
        assert latency_ms == 0, f"Future timestamp {start_ts} did not result in 0ms latency."
    # If the start time is in the past, it must be close to the actual elapsed time.
    else:
        # Check if the latency is within the expected range, plus a small tolerance
        # (e.g., 20ms). The true measured latency should fall between what was
        # possible just before the call and just after.
        assert latency_ms >= expected_ms_min - 20
        assert latency_ms <= expected_ms_max + 20


@pytest.mark.ci
@settings(max_examples=50, deadline=None)
@given(endpoint=safe_text, latency=latencies, ttl=ttls)
def test_property_based_legacy_signature(capture_ttl_emit, endpoint, latency, ttl):
    """Property-based test for the legacy signature format."""
    emit_latency_trace(endpoint, latency, r="fake", ttl_seconds=ttl)
    assert len(capture_ttl_emit) == 1
    _, kwargs = capture_ttl_emit[0]
    expected_key_part = f"latency:{endpoint}"
    assert kwargs.get("key") == expected_key_part
    assert kwargs.get("ttl") == ttl
    # Check if value is a string representation of a float
    try:
        # Check that the string value is close to the input float (due to float precision)
        float_val = float(kwargs.get("value", ""))
        assert abs(float_val - latency) < 0.01
        assert isinstance(kwargs.get("value"), str)
    except (ValueError, TypeError):
        pytest.fail(f"Legacy value payload was not a valid float string: {kwargs.get('value')}")


# === Concurrent Property-Based Fuzzing (Marked as Nightly) ===

# Strategy for request IDs: random UUIDs combined with the thread index for guaranteed
# uniqueness checks
concurrent_req_id_strategy = st.builds(
    lambda thread_index, hex_part: f"T{thread_index}-{hex_part}",
    thread_index=st.integers(min_value=0, max_value=4),  # 5 threads
    hex_part=st.uuids().map(lambda u: u.hex[:8]),
)


def _concurrent_property_worker(stage, request_id, start_ts, ttl):
    """Worker function to run a single fuzzed emit in a thread."""
    try:
        emit_latency_trace(stage, request_id, start_ts, r="concurrent-fuzz", ttl_seconds=ttl)
    except Exception as e:
        logging.error(
            "Concurrent fuzzing error in thread %s for req_id %s: %s",
            threading.get_ident(),
            request_id,
            e,
        )
        # Note: If the test fails a hard assertion, it will fail the whole suite later.


@pytest.mark.nightly  # Changed from @pytest.mark.slow to @pytest.mark.nightly
@settings(max_examples=100, deadline=None)
@given(
    stage=safe_text,
    # Generate 5 sets of random inputs for 5 threads
    inputs=st.lists(
        st.tuples(concurrent_req_id_strategy, timestamps, ttls),
        min_size=5,
        max_size=5,
        unique_by=lambda x: x[0],  # Ensure unique request ID prefixes
    ),
)
def test_property_based_concurrent_new_signature(capture_ttl_emit, stage, inputs):
    """
    Property-based test combined with concurrency (fuzzing race conditions).
    Runs 5 threads, each emitting a fuzzed trace.
    """
    threads = []

    # Kick off the threads
    for i in range(len(inputs)):
        # Extract the fuzzed inputs for this thread
        fuzzed_req_id, fuzzed_ts, fuzzed_ttl = inputs[i]

        thread = threading.Thread(
            target=_concurrent_property_worker,
            args=(stage, fuzzed_req_id, fuzzed_ts, fuzzed_ttl),
        )
        threads.append(thread)
        thread.start()

    # Wait for all threads to complete
    for thread in threads:
        thread.join(timeout=10)

    # Validation: Check that exactly 5 traces were captured and all keys are unique.
    assert len(capture_ttl_emit) == len(
        inputs
    ), "Incorrect number of traces captured under concurrency."

    # Final check: Keys must be unique (ensuring no trace was overwritten/lost)
    captured_keys = set(kw["key"] for _, kw in capture_ttl_emit)
    assert len(captured_keys) == len(inputs), (
        "Non-unique keys detected during concurrent property test, indicating a "
        "race condition or overwrite."
    )


# === Long-Running Soak Test (Marked as Nightly with Environment Check) ===


@pytest.mark.nightly  # Changed from @pytest.mark.slow to @pytest.mark.nightly
def test_soak_test_memory_leak():
    """
    Long-running soak test to simulate thousands of traces over time.
    Verifies that the global data structure (_ttl_data) handles high volume
    without leading to unbounded memory growth (i.e., it relies on TTL logic
    to naturally manage size, which is checked indirectly here).
    Skipped unless the RUN_SOAK_TEST environment variable is set.
    """
    # Check environment variable to skip test on quick CI runs
    if not os.getenv("RUN_SOAK_TEST"):
        pytest.skip("Skipping soak test. Set RUN_SOAK_TEST=1 to run this test.")

    from app.telemetry.ttl_emit import _ttl_data

    # Use a large number of traces to stress the system
    num_emits = 50000

    start_time = time.time()

    # Emit traces rapidly
    for i in range(num_emits):
        request_id = f"soak-req-{i}-{uuid.uuid4().hex[:4]}"
        # Simulate a 50ms latency
        emit_latency_trace("soak_test_leak_check", request_id, time.time() - 0.05, r="soak_session")

    end_time = time.time()
    duration = end_time - start_time
    logging.info(f"Soak test completed {num_emits} emits in {duration:.2f} seconds.")

    # Memory Leak Check:
    # Since all 50,000 traces have the default TTL of 300 seconds and were emitted
    # almost instantly, all of them should still be present in _ttl_data.
    # The crucial check here is that the process *survived* the high-volume burst.

    # 1. Assert Stability (Size Check)
    # The size must exactly match the number of non-expired items. Since we didn't wait
    # for expiration, this should be the total number of items emitted.
    current_size = len(_ttl_data)
    assert current_size == num_emits, (
        f"Expected _ttl_data size to be {num_emits} after burst, but found "
        f"{current_size}. Potential trace loss."
    )

    # 2. Check Expiry Indicator (If the test runs for longer, it would be checked here)
    # We rely on the size being stable and the system surviving the burst, which is a
    # key stability check.
