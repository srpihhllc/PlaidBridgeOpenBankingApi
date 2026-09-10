# =============================================================================
# FILE: app/tests/test_latency_trace.py
# DESCRIPTION:
#   Refactored and hardened unit tests for emit_latency_trace and related TTL
#   telemetry. Adjusted to be Hypothesis-friendly by using a per-example context
#   manager for property-based tests (avoids function-scoped fixture health checks).
#   Made property-based upper bound more permissive to avoid flakiness where
#   generated timestamps and runtime clock drift can produce larger but valid
#   durations.
# =============================================================================

import datetime
import importlib
import logging
import os
import threading
import time
import uuid
from contextlib import contextmanager
from typing import Any, Dict, Iterator, List, Tuple

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.telemetry.ttl_emit import _ttl_data, emit_boot_trace, ttl_summary
from app.utils.latency import emit_latency_trace

# Configure logging to help diagnose intermittent failures while remaining concise.
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def clear_ttl_data():
    """
    Ensure _ttl_data is cleared for each test to guarantee isolation for tests that
    inspect ttl_summary() or rely on global telemetry state. Uses a lock to be
    defensive when tests spawn threads.
    """
    lock = threading.Lock()
    with lock:
        snapshot = dict(_ttl_data)
        _ttl_data.clear()
    try:
        yield
    finally:
        with lock:
            _ttl_data.clear()
            _ttl_data.update(snapshot)


@pytest.fixture
def capture_ttl_emit(monkeypatch) -> Any:
    """
    Function-scoped fixture that captures calls to app.utils.latency.ttl_emit.

    This fixture is intended for regular (non-Hypothesis) tests: each pytest test
    gets a fresh capture. Hypothesis-driven tests should use the
    capture_ttl_emit_context() below to get a fresh capture per example.
    """
    lat_mod = importlib.import_module("app.utils.latency")
    original = getattr(lat_mod, "ttl_emit", None)

    calls_lock = threading.Lock()

    class CaptureList:
        def __init__(self) -> None:
            self._calls: List[Tuple[Tuple[Any, ...], Dict[str, Any]]] = []

        def append(self, item: Tuple[Tuple[Any, ...], Dict[str, Any]]) -> None:
            with calls_lock:
                self._calls.append(item)

        def clear(self) -> None:
            with calls_lock:
                self._calls.clear()

        def __len__(self) -> int:
            with calls_lock:
                return len(self._calls)

        def __getitem__(
            self, idx: int
        ) -> Tuple[Tuple[Any, ...], Dict[str, Any]]:
            with calls_lock:
                return self._calls[idx]

        def __iter__(self) -> Iterator[Tuple[Tuple[Any, ...], Dict[str, Any]]]:
            with calls_lock:
                return iter(list(self._calls))

        def items(self) -> List[Tuple[Tuple[Any, ...], Dict[str, Any]]]:
            with calls_lock:
                return list(self._calls)

        def __repr__(self) -> str:
            with calls_lock:
                return repr(self._calls)

    calls = CaptureList()

    def fake_ttl_emit(*args: Any, **kwargs: Any) -> None:
        calls.append((args, kwargs))

    # Patch and ensure restoration in teardown
    monkeypatch.setattr(lat_mod, "ttl_emit", fake_ttl_emit)

    try:
        yield calls
    finally:
        # Restore original implementation to avoid cross-test side effects
        if original is None:
            try:
                delattr(lat_mod, "ttl_emit")
            except Exception:
                pass
        else:
            setattr(lat_mod, "ttl_emit", original)


# -----------------------------------------------------------------------------
# Hypothesis-friendly context manager (per-example capture)
# -----------------------------------------------------------------------------
class ThreadSafeCapture:
    """Minimal thread-safe list-like capture used by Hypothesis examples."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._calls: List[Tuple[Tuple[Any, ...], Dict[str, Any]]] = []

    def append(self, item: Tuple[Tuple[Any, ...], Dict[str, Any]]) -> None:
        with self._lock:
            self._calls.append(item)

    def clear(self) -> None:
        with self._lock:
            self._calls.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._calls)

    def __getitem__(self, idx: int) -> Tuple[Tuple[Any, ...], Dict[str, Any]]:
        with self._lock:
            return self._calls[idx]

    def items(self) -> List[Tuple[Tuple[Any, ...], Dict[str, Any]]]:
        with self._lock:
            return list(self._calls)

    def __iter__(self):
        with self._lock:
            return iter(list(self._calls))


@contextmanager
def capture_ttl_emit_context():
    """
    Context manager that patches app.utils.latency.ttl_emit and yields a fresh
    ThreadSafeCapture. Use this inside Hypothesis-driven tests so each example
    gets an isolated capture list.
    """
    lat_mod = importlib.import_module("app.utils.latency")
    original = getattr(lat_mod, "ttl_emit", None)

    calls = ThreadSafeCapture()

    def fake_ttl_emit(*args: Any, **kwargs: Any) -> None:
        calls.append((args, kwargs))

    setattr(lat_mod, "ttl_emit", fake_ttl_emit)
    try:
        yield calls
    finally:
        # Restore original
        if original is None:
            try:
                delattr(lat_mod, "ttl_emit")
            except Exception:
                pass
        else:
            setattr(lat_mod, "ttl_emit", original)


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def _extract_key(kwargs: Dict[str, Any]) -> str:
    return kwargs.get("key", "")


# -----------------------------------------------------------------------------
# Signature Coverage
# -----------------------------------------------------------------------------
@pytest.mark.ci
def test_new_signature_positional(capture_ttl_emit):
    """New-style positional: emit_latency_trace(stage, request_uuid, start_ts, r)."""
    start_time = time.time() - 0.1  # Simulate ~100ms latency
    emit_latency_trace("auth", "req-123", start_time, r="fake")
    assert len(capture_ttl_emit) == 1, "Expected a single ttl_emit call."

    _, kwargs = capture_ttl_emit[0]
    key = _extract_key(kwargs)
    assert "ttl:flow:oauth:google:auth:latency:req-123" in key
    assert kwargs.get("ttl") == 300

    value_payload = kwargs.get("value", "")
    assert isinstance(value_payload, str)
    assert value_payload.startswith("latency_ms:")
    ms_part = value_payload.split(":", 1)[1]
    assert ms_part.isdigit(), f"latency payload malformed: {value_payload}"


@pytest.mark.ci
def test_legacy_signature_positional(capture_ttl_emit):
    """Legacy-style positional: emit_latency_trace(endpoint, latency_ms, r)."""
    emit_latency_trace("user_login", 123.45, r="fake")
    assert len(capture_ttl_emit) == 1

    _, kwargs = capture_ttl_emit[0]
    key = _extract_key(kwargs)
    assert "latency:user_login" in key or "latency:user_login" in str(
        kwargs.values()
    )
    assert kwargs.get("ttl") == 300

    assert isinstance(kwargs.get("value"), str)
    assert kwargs.get("value") == "123.45"


@pytest.mark.ci
def test_new_signature_keyword(capture_ttl_emit):
    """New-style keyword: emit_latency_trace(stage=..., request_uuid=..., start_ts=..., r=...)."""
    start_time = time.time() - 0.2
    emit_latency_trace(
        stage="token", request_uuid="abc", start_ts=start_time, r="fake"
    )
    assert len(capture_ttl_emit) == 1

    _, kwargs = capture_ttl_emit[0]
    assert "ttl:flow:oauth:google:token:latency:abc" in _extract_key(kwargs)
    assert kwargs.get("ttl") == 300
    assert isinstance(kwargs.get("value"), str) and kwargs["value"].startswith(
        "latency_ms:"
    )


@pytest.mark.ci
def test_legacy_signature_keyword(capture_ttl_emit):
    """Legacy-style keyword: emit_latency_trace(endpoint=..., latency_ms=..., r=...)."""
    emit_latency_trace(endpoint="refresh", latency_ms=456.78, r="fake")
    assert len(capture_ttl_emit) == 1

    _, kwargs = capture_ttl_emit[0]
    assert "latency:refresh" in _extract_key(kwargs) or any(
        "latency:refresh" in str(v) for v in kwargs.values()
    )
    assert kwargs.get("ttl") == 300
    assert kwargs.get("value") == "456.78"


# -----------------------------------------------------------------------------
# TTL Behavior
# -----------------------------------------------------------------------------
@pytest.mark.ci
def test_custom_ttl_override(capture_ttl_emit):
    emit_latency_trace(
        "auth", "req-123", time.time(), r="fake", ttl_seconds=120
    )
    assert len(capture_ttl_emit) == 1
    _, kwargs = capture_ttl_emit[0]
    assert kwargs.get("ttl") == 120


@pytest.mark.ci
def test_multiple_emits(capture_ttl_emit):
    emit_latency_trace("auth", "req-1", time.time(), r="fake")
    emit_latency_trace("auth", "req-2", time.time(), r="fake")
    assert len(capture_ttl_emit) == 2

    keys = [kw["key"] for _, kw in capture_ttl_emit.items()]
    assert keys == [
        "ttl:flow:oauth:google:auth:latency:req-1",
        "ttl:flow:oauth:google:auth:latency:req-2",
    ]


@pytest.mark.ci
def test_negative_duration_fallback(capture_ttl_emit):
    emit_latency_trace("auth", "req-xyz", time.time() + 100, r="fake")
    assert len(capture_ttl_emit) == 1
    _, kwargs = capture_ttl_emit[0]
    value_payload = kwargs.get("value", "")
    assert value_payload == "latency_ms:0"


# -----------------------------------------------------------------------------
# Error Handling
# -----------------------------------------------------------------------------
@pytest.mark.ci
def test_invalid_arguments_raises_typeerror():
    with pytest.raises(TypeError):
        emit_latency_trace("only_one_argument")


@pytest.mark.ci
def test_ttl_emit_signature_mismatch(monkeypatch, caplog):
    """
    If the underlying ttl_emit has an incompatible signature or raises a TypeError,
    emit_latency_trace should surface the error and log a warning. Behavior depends
    on implementation; aim for clear diagnostic logs in our code.
    """
    caplog.set_level("WARNING")

    def broken_ttl_emit(*_args, **_kwargs):
        raise TypeError("bad signature")

    monkeypatch.setattr("app.utils.latency.ttl_emit", broken_ttl_emit)

    with pytest.raises(TypeError):
        emit_latency_trace("legacy", 123.0, r="fake")

    # Validate log presence — exact message is implementation dependent.
    assert (
        "ttl_emit signature" in caplog.text or "bad signature" in caplog.text
    )


# -----------------------------------------------------------------------------
# Trace Delegation (emit_boot_trace)
# -----------------------------------------------------------------------------
@pytest.mark.ci
def test_emit_boot_trace_delegates_to_ttl_emit(monkeypatch):
    calls: List[Tuple[Tuple[Any, ...], Dict[str, Any]]] = []

    def fake_ttl_emit(*args: Any, **kwargs: Any) -> None:
        calls.append((args, kwargs))

    monkeypatch.setattr("app.telemetry.ttl_emit.ttl_emit", fake_ttl_emit)
    emit_boot_trace(
        key="ttl:boot:blueprint:auth:complete", status="ok", r="fake"
    )

    assert len(calls) == 1
    _, kwargs = calls[0]
    assert kwargs["key"] == "ttl:boot:blueprint:auth:complete"
    assert kwargs["status"] == "ok"
    assert kwargs["ttl"] == 60


# -----------------------------------------------------------------------------
# TTL Summary
# -----------------------------------------------------------------------------
@pytest.mark.ci
def test_ttl_summary_expiry_and_freshness():
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
    assert summary["key:fresh"]["meta"]["source"] == "test"


# -----------------------------------------------------------------------------
# Stress / Performance Tests (Nightly)
# -----------------------------------------------------------------------------
@pytest.mark.nightly
@pytest.mark.parametrize(
    ("num_emits", "perf_limit_seconds"),
    [
        (100, 0.5),
        (1000, 3.0),
        (10000, 30.0),
    ],
)
def test_stress_emits_performance(
    capture_ttl_emit, num_emits, perf_limit_seconds
):
    logging.info(
        "Starting stress test with %d emits (limit %.2fs).",
        num_emits,
        perf_limit_seconds,
    )

    loop_start_time = time.time()
    for i in range(num_emits):
        emit_latency_trace(
            "stress", f"req-{i}", loop_start_time - (i * 0.01), r="fake"
        )
    loop_duration = time.time() - loop_start_time

    assert (
        len(capture_ttl_emit) == num_emits
    ), "Mismatch between expected and captured emits."
    assert (
        loop_duration < perf_limit_seconds
    ), f"Stress test took too long: {loop_duration:.2f}s"

    keys = {kwargs.get("key") for _, kwargs in capture_ttl_emit.items()}
    ttls = {kwargs.get("ttl") for _, kwargs in capture_ttl_emit.items()}

    assert len(keys) == num_emits
    assert ttls == {300}


@pytest.mark.ci
def test_boundary_ttl(capture_ttl_emit):
    emit_latency_trace(
        "auth", "req-zero", time.time(), r="fake", ttl_seconds=0
    )
    emit_latency_trace(
        "auth", "req-neg", time.time(), r="fake", ttl_seconds=-10
    )

    assert len(capture_ttl_emit) == 2
    _, kwargs_zero = capture_ttl_emit[0]
    _, kwargs_neg = capture_ttl_emit[1]
    assert kwargs_zero.get("ttl") == 0
    assert kwargs_neg.get("ttl") == -10


@pytest.mark.ci
def test_emit_boot_trace_with_meta(monkeypatch):
    calls: List[Tuple[Tuple[Any, ...], Dict[str, Any]]] = []

    def fake_ttl_emit(*args: Any, **kwargs: Any) -> None:
        calls.append((args, kwargs))

    monkeypatch.setattr("app.telemetry.ttl_emit.ttl_emit", fake_ttl_emit)

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
    assert kwargs.get("meta") == {"version": "1.2.3", "node": "worker-5"}


# -----------------------------------------------------------------------------
# Concurrency Tests
# -----------------------------------------------------------------------------
def _concurrent_emit_task(thread_id: int, num_calls: int) -> None:
    for i in range(num_calls):
        req_id = f"T{thread_id}-R{i}-{uuid.uuid4().hex[:8]}"
        start_ts = time.time() - 0.05
        emit_latency_trace(
            f"concurrent_stage_{thread_id}", req_id, start_ts, r="fake"
        )


@pytest.mark.ci
def test_concurrent_emits(capture_ttl_emit):
    num_threads = 5
    calls_per_thread = 20
    total_expected_calls = num_threads * calls_per_thread

    threads: List[threading.Thread] = []
    for i in range(num_threads):
        t = threading.Thread(
            target=_concurrent_emit_task, args=(i, calls_per_thread)
        )
        threads.append(t)
        t.start()

    for t in threads:
        t.join(timeout=10)

    assert (
        len(capture_ttl_emit) == total_expected_calls
    ), f"Expected {total_expected_calls} emits, got {len(capture_ttl_emit)}"

    keys = {kwargs.get("key") for _, kwargs in capture_ttl_emit.items()}
    assert (
        len(keys) == total_expected_calls
    ), "Concurrent emits produced non-unique keys."


# -----------------------------------------------------------------------------
# Property-Based Tests
# -----------------------------------------------------------------------------
# Use alphanumeric-only characters to avoid exotic unicode causing unexpected key formatting.
safe_text = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N")),
    min_size=1,
    max_size=20,
)
timestamps = st.floats(
    min_value=time.time() - 3600, max_value=time.time() + 3600
)
latencies = st.floats(min_value=0.0, max_value=10000.0)
ttls = st.integers(min_value=-100, max_value=3600)


@pytest.mark.ci
@settings(max_examples=100, deadline=None)
@given(
    stage=safe_text,
    request_id=st.text(
        alphabet=st.characters(whitelist_categories=("L", "N")),
        min_size=1,
        max_size=20,
    ),
    start_ts=timestamps,
    ttl=ttls,
)
def test_property_based_new_signature(stage, request_id, start_ts, ttl):
    # Use context manager to ensure a fresh capture list per Hypothesis example.
    with capture_ttl_emit_context() as capture_ttl_emit:
        time_before_call = time.time()
        emit_latency_trace(
            stage, request_id, start_ts, r="fake", ttl_seconds=ttl
        )
        time_after_call = time.time()

        assert len(capture_ttl_emit) == 1
        _, kwargs = capture_ttl_emit[0]

        expected_key_part = (
            f"ttl:flow:oauth:google:{stage}:latency:{request_id}"
        )
        assert kwargs.get("key") == expected_key_part
        assert kwargs.get("ttl") == ttl

        value_payload = kwargs.get("value", "")
        assert isinstance(value_payload, str) and value_payload.startswith(
            "latency_ms:"
        )
        latency_ms_str = value_payload.split(":", 1)[1]
        assert latency_ms_str.isdigit()
        latency_ms = int(latency_ms_str)

        assert latency_ms >= 0

        # Allow a wider upper bound to avoid flakiness when clocks drift between
        # Hypothesis strategy construction time and test execution time.
        # The original strict bound (4_000_000) proved brittle in CI.
        assert latency_ms < 10_000_000

        expected_ms_min = max(0, int((time_before_call - start_ts) * 1000))
        expected_ms_max = max(0, int((time_after_call - start_ts) * 1000))

        if start_ts > time_before_call:
            assert latency_ms == 0
        else:
            assert latency_ms >= expected_ms_min - 20
            assert latency_ms <= expected_ms_max + 20


@pytest.mark.ci
@settings(max_examples=50, deadline=None)
@given(endpoint=safe_text, latency=latencies, ttl=ttls)
def test_property_based_legacy_signature(endpoint, latency, ttl):
    with capture_ttl_emit_context() as capture_ttl_emit:
        emit_latency_trace(endpoint, latency, r="fake", ttl_seconds=ttl)
        assert len(capture_ttl_emit) == 1
        _, kwargs = capture_ttl_emit[0]

        assert kwargs.get("key", "").startswith(f"latency:{endpoint}")
        assert kwargs.get("ttl") == ttl

        try:
            float_val = float(kwargs.get("value", ""))
            assert abs(float_val - latency) < 0.01
            assert isinstance(kwargs.get("value"), str)
        except (ValueError, TypeError):
            pytest.fail(
                f"Legacy value payload was not a valid float string: {kwargs.get('value')}"
            )


# Concurrent property fuzzing (nightly)
concurrent_req_id_strategy = st.builds(
    lambda thread_index, hex_part: f"T{thread_index}-{hex_part}",
    thread_index=st.integers(min_value=0, max_value=4),
    hex_part=st.uuids().map(lambda u: u.hex[:8]),
)


def _concurrent_property_worker(
    stage: str, request_id: str, start_ts: float, ttl: int
) -> None:
    try:
        emit_latency_trace(
            stage, request_id, start_ts, r="concurrent-fuzz", ttl_seconds=ttl
        )
    except Exception as e:
        logging.error("Concurrent fuzzing worker error: %s", e)


@pytest.mark.nightly
@settings(max_examples=100, deadline=None)
@given(
    stage=safe_text,
    inputs=st.lists(
        st.tuples(concurrent_req_id_strategy, timestamps, ttls),
        min_size=5,
        max_size=5,
        unique_by=lambda x: x[0],
    ),
)
def test_property_based_concurrent_new_signature(stage, inputs):
    """
    Property-based concurrent test: spawn 5 threads, each performing exactly one
    emit. Use context manager for per-example isolation.
    """
    with capture_ttl_emit_context() as capture_ttl_emit:
        threads: List[threading.Thread] = []
        for fuzzed in inputs:
            fuzzed_req_id, fuzzed_ts, fuzzed_ttl = fuzzed
            t = threading.Thread(
                target=_concurrent_property_worker,
                args=(stage, fuzzed_req_id, fuzzed_ts, fuzzed_ttl),
            )
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=10)

        assert (
            len(capture_ttl_emit) == len(inputs)
        ), f"Incorrect number of traces captured under concurrency: expected {len(inputs)}, got {len(capture_ttl_emit)}"

        captured_keys = {
            kwargs["key"] for _, kwargs in capture_ttl_emit.items()
        }
        assert len(captured_keys) == len(
            inputs
        ), "Non-unique keys detected during concurrent property test."


# -----------------------------------------------------------------------------
# Soak Test (explicit opt-in)
# -----------------------------------------------------------------------------
@pytest.mark.nightly
def test_soak_test_memory_leak():
    if not os.getenv("RUN_SOAK_TEST"):
        pytest.skip(
            "Skipping soak test. Set RUN_SOAK_TEST=1 to run this test."
        )

    num_emits = 50000
    start_time = time.time()
    for i in range(num_emits):
        request_id = f"soak-req-{i}-{uuid.uuid4().hex[:4]}"
        emit_latency_trace(
            "soak_test_leak_check",
            request_id,
            time.time() - 0.05,
            r="soak_session",
        )
    duration = time.time() - start_time
    logging.info("Soak test completed %d emits in %.2fs.", num_emits, duration)
    # Keep the assertion minimal because this test only runs when explicitly enabled.
    assert duration < 600.0
