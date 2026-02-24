# app/cockpit/lib/ttl.py

import time
from functools import wraps

# Simple in-memory TTL cache
_cache_store: dict[str, object] = {}


def ttl_cache(seconds=30):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            key = (fn.__name__, args, frozenset(kwargs.items()))
            now = time.time()
            cached = _cache_store.get(key)

            if cached:
                value, timestamp = cached
                if now - timestamp < seconds:
                    return value

            result = fn(*args, **kwargs)
            _cache_store[key] = (result, now)
            return result

        return wrapper

    return decorator
