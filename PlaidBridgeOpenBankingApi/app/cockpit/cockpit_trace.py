from typing import Any


def trace_log(*args: Any, **kwargs: Any) -> None:
    # no-op logger used during tests

    return None


def ttl_emitter(*args: Any, **kwargs: Any) -> None:
    # no-op TTL emitter used during tests

    return None
