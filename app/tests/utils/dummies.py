# =============================================================================
# FILE: app/tests/utils/dummies.py
# DESCRIPTION: Centralized stub classes, registry, and assertion helpers for
#              external SDKs and in‑memory Redis used across the test harness.
# =============================================================================

# Global registry of all dummy instances (DummyContext, DummyRedis, etc.)
_DUMMY_REGISTRY = []


# =============================================================================
# DummyContext — Generic SDK Stub
# =============================================================================


class DummyContext:
    """
    A dummy object used to stub external SDK clients (like Plaid, Boto3, Mail).
    Logs all method calls for assertion and inspection.
    """

    def __init__(self):
        self.calls = []
        _DUMMY_REGISTRY.append(self)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def __call__(self, *a, **k):
        self.calls.append(("__call__", a, k))
        return self

    def __getattr__(self, name):
        def _method(*a, **k):
            self.calls.append((name, a, k))
            return self

        return _method


# =============================================================================
# DummyRedis — Unified In-Memory Redis Stub
# =============================================================================


class DummyRedis:
    """
    Unified in-memory Redis stub used across the entire test harness.
    Behaves like a minimal Redis client for rate limiting, telemetry,
    identity events, and queue operations.
    """

    def __init__(self):
        self.store = {}
        self.lists = {}
        _DUMMY_REGISTRY.append(self)

    # -----------------------------
    # Key-value operations
    # -----------------------------
    def setex(self, key, ttl, val):
        self.store[key] = (val, ttl)

    def get(self, key):
        return self.store.get(key, (None, None))[0]

    def ttl(self, key):
        return self.store.get(key, (None, -1))[1]

    def keys(self, pattern="*"):
        if pattern == "*":
            return list(self.store.keys()) + list(self.lists.keys())
        import re

        pattern_re = pattern.replace(".", r"\.").replace("*", ".*")
        return [
            k for k in list(self.store.keys()) + list(self.lists.keys()) if re.match(pattern_re, k)
        ]

    # -----------------------------
    # Pipeline
    # -----------------------------
    def pipeline(self):
        parent = self

        class _Pipe:
            def __init__(self):
                self.ops = []

            def incr(self, key, amount=1):
                cur = parent.store.get(key, (0, None))[0]
                try:
                    cur_int = int(cur)
                except Exception:
                    cur_int = 0
                cur_int += amount
                parent.store[key] = (
                    str(cur_int),
                    parent.store.get(key, (None, None))[1],
                )
                self.ops.append(("incr", key, amount))
                return cur_int

            def expire(self, key, seconds):
                val, _ = parent.store.get(key, (None, None))
                parent.store[key] = (val, seconds)
                self.ops.append(("expire", key, seconds))
                return True

            def execute(self):
                results = [None] * len(self.ops)
                self.ops.clear()
                return results

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        return _Pipe()

    # -----------------------------
    # List operations
    # -----------------------------
    def rpush(self, key, *values):
        lst = self.lists.setdefault(key, [])
        for v in values:
            lst.append(v if isinstance(v, bytes | str) else str(v))
        return len(lst)

    def lpush(self, key, *values):
        lst = self.lists.setdefault(key, [])
        for v in values:
            lst.insert(0, v if isinstance(v, bytes | str) else str(v))
        return len(lst)

    def lrange(self, key, start, end):
        lst = self.lists.get(key, [])
        slice_end = None if end == -1 else end + 1
        sub = lst[start:slice_end]
        out = []
        for v in sub:
            out.append(v if isinstance(v, bytes) else str(v).encode("utf-8"))
        return out

    # -----------------------------
    # Deletion & flush
    # -----------------------------
    def delete(self, key):
        self.store.pop(key, None)
        self.lists.pop(key, None)
        return 1

    def flushdb(self):
        self.store.clear()
        self.lists.clear()


# =============================================================================
# Assertion Helpers
# =============================================================================


def assert_called_with(dummy, method_name, *args, **kwargs):
    assert any(
        call[0] == method_name and call[1] == args and call[2] == kwargs for call in dummy.calls
    ), (
        f"Expected call to '{method_name}' with args {args} and kwargs {kwargs}, "
        f"but found calls: {dummy.calls}"
    )


def assert_called_once_with(dummy, method_name, *args, **kwargs):
    matches = [
        call
        for call in dummy.calls
        if call[0] == method_name and call[1] == args and call[2] == kwargs
    ]
    assert len(matches) == 1, (
        f"Expected exactly one call to '{method_name}' with args {args} and kwargs {kwargs}, "
        f"but found {len(matches)} matches in calls: {dummy.calls}"
    )


def assert_not_called(dummy, method_name):
    matches = [call for call in dummy.calls if call[0] == method_name]
    assert (
        not matches
    ), f"Expected no calls to '{method_name}', but found {len(matches)} calls: {matches}"


def assert_call_count(dummy, method_name, expected_count):
    matches = [call for call in dummy.calls if call[0] == method_name]
    actual_count = len(matches)
    assert actual_count == expected_count, (
        f"Expected method '{method_name}' to be called {expected_count} times, "
        f"but it was called {actual_count} times. Found calls: {matches}"
    )


# =============================================================================
# Global Reset
# =============================================================================


def reset_all_dummies():
    """Clear the call logs and state on all registered dummy instances."""
    for dummy in _DUMMY_REGISTRY:
        if hasattr(dummy, "calls"):
            dummy.calls.clear()
        if hasattr(dummy, "store"):
            dummy.store.clear()
        if hasattr(dummy, "lists"):
            dummy.lists.clear()
