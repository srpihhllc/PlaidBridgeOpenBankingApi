#/home/srpihhllc/PlaidBridgeOpenBankingApi/app/tests/test_sync_worker.py

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import app.workers.sync_worker as worker


# ----------------------------------------------------------------------
# Tests for _get_extension() & _get_redis_client()
# ----------------------------------------------------------------------

def test_get_extension_returns_none_when_missing():
    app = SimpleNamespace()
    assert worker._get_extension(app, "redis_client") is None


def test_get_extension_reads_dict():
    redis = object()
    app = SimpleNamespace(extensions={"redis_client": redis})
    assert worker._get_extension(app, "redis_client") is redis


def test_get_extension_reads_object_attribute():
    redis = object()
    app = SimpleNamespace(extensions=SimpleNamespace(redis_client=redis))
    assert worker._get_extension(app, "redis_client") is redis


def test_get_redis_client_prefers_app_attribute():
    redis = object()
    app = SimpleNamespace(redis_client=redis)
    assert worker._get_redis_client(app) is redis


def test_get_redis_client_uses_extension():
    redis = object()
    app = SimpleNamespace(extensions={"redis_client": redis})
    assert worker._get_redis_client(app) is redis


def test_get_redis_client_returns_none_when_helper_import_fails(monkeypatch):
    app = SimpleNamespace()

    def fake_import(*args, **kwargs):
        raise ImportError("Redis helper unavailable")

    monkeypatch.setattr("builtins.__import__", fake_import)
    assert worker._get_redis_client(app) is None


def test_get_redis_client_returns_none_when_helper_raises(monkeypatch):
    app = SimpleNamespace()

    def fake_get_redis_client():
        raise RuntimeError("Redis unavailable")

    monkeypatch.setattr(
        "app.extensions.get_redis_client",
        fake_get_redis_client,
        raising=False,
    )
    assert worker._get_redis_client(app) is None


# ----------------------------------------------------------------------
# Tests for _decode_job()
# ----------------------------------------------------------------------

def test_decode_job_decodes_redis_tuple_with_bytes():
    result = worker._decode_job(
        (b"sync:jobs", b'{"job_id": "123", "type": "account"}')
    )
    assert result == {"job_id": "123", "type": "account"}


def test_decode_job_decodes_string_json():
    result = worker._decode_job('{"job_id": "123"}')
    assert result == {"job_id": "123"}


def test_decode_job_preserves_invalid_json():
    result = worker._decode_job((b"sync:jobs", b"not-json"))
    assert result == {"raw": "not-json"}


def test_decode_job_wraps_non_dictionary_json():
    assert worker._decode_job("[1, 2, 3]") == {"raw": [1, 2, 3]}


def test_decode_job_handles_bytearray():
    result = worker._decode_job(bytearray(b'{"status": "ok"}'))
    assert result == {"status": "ok"}


def test_decode_job_handles_none():
    assert worker._decode_job(None) == {"raw": None}


# ----------------------------------------------------------------------
# Tests for process_job()
# ----------------------------------------------------------------------

def test_process_job_logs_and_sleeps(monkeypatch):
    sleep = MagicMock()
    monkeypatch.setattr(worker.time, "sleep", sleep)

    worker.process_job({"job_id": "job-1", "type": "transactions"})
    sleep.assert_called_once_with(0.1)


# ----------------------------------------------------------------------
# Tests for main()
# ----------------------------------------------------------------------

def test_main_without_redis_runs_limited_noop_loop(monkeypatch):
    app = SimpleNamespace()
    monkeypatch.setattr(worker, "create_app", lambda: app)
    monkeypatch.setattr(worker, "_get_redis_client", lambda app: None)

    sleep = MagicMock()
    monkeypatch.setattr(worker.time, "sleep", sleep)

    worker.main(max_iterations=3)

    assert sleep.call_count == 3
    sleep.assert_called_with(worker.POLL_INTERVAL)


def test_main_processes_job(monkeypatch):
    redis = MagicMock()
    redis.blpop.return_value = (
        b"sync:jobs",
        b'{"job_id": "job-1", "type": "account"}',
    )
    app = SimpleNamespace(redis_client=redis)

    monkeypatch.setattr(worker, "create_app", lambda: app)

    process_job = MagicMock()
    monkeypatch.setattr(worker, "process_job", process_job)

    worker.main(max_iterations=1)

    redis.blpop.assert_called_once_with(worker.REDIS_LIST_KEY, timeout=5)
    process_job.assert_called_once_with({"job_id": "job-1", "type": "account"})


def test_main_sleeps_when_queue_is_empty(monkeypatch):
    redis = MagicMock()
    redis.blpop.return_value = None
    app = SimpleNamespace(redis_client=redis)

    monkeypatch.setattr(worker, "create_app", lambda: app)

    sleep = MagicMock()
    monkeypatch.setattr(worker.time, "sleep", sleep)

    worker.main(max_iterations=1)
    sleep.assert_called_once_with(worker.POLL_INTERVAL)


def test_main_handles_blpop_without_timeout(monkeypatch):
    """Tests fallback when the Redis client throws TypeError on timeout argument."""
    redis = MagicMock()
    redis.blpop.side_effect = TypeError("timeout unsupported")
    app = SimpleNamespace(redis_client=redis)

    monkeypatch.setattr(worker, "create_app", lambda: app)

    sleep = MagicMock()
    monkeypatch.setattr(worker.time, "sleep", sleep)

    worker.main(max_iterations=1)

    redis.blpop.assert_called_once_with(worker.REDIS_LIST_KEY, timeout=5)
    sleep.assert_called_once_with(worker.POLL_INTERVAL)


def test_main_continues_when_process_job_fails(monkeypatch):
    redis = MagicMock()
    redis.blpop.return_value = (b"sync:jobs", b'{"job_id": "job-1"}')
    app = SimpleNamespace(redis_client=redis)

    monkeypatch.setattr(worker, "create_app", lambda: app)

    process_job = MagicMock(side_effect=RuntimeError("processing failed"))
    monkeypatch.setattr(worker, "process_job", process_job)

    worker.main(max_iterations=1)
    process_job.assert_called_once()


def test_main_handles_keyboard_interrupt(monkeypatch):
    redis = MagicMock()
    redis.blpop.side_effect = KeyboardInterrupt
    app = SimpleNamespace(redis_client=redis)

    monkeypatch.setattr(worker, "create_app", lambda: app)
    worker.main(max_iterations=None)


def test_main_no_redis_handles_keyboard_interrupt(monkeypatch):
    app = SimpleNamespace()
    monkeypatch.setattr(worker, "create_app", lambda: app)
    monkeypatch.setattr(worker, "_get_redis_client", lambda app: None)

    def interrupt_sleep(_):
        raise KeyboardInterrupt

    monkeypatch.setattr(worker.time, "sleep", interrupt_sleep)
    worker.main(max_iterations=None)


def test_main_raises_when_create_app_is_unavailable(monkeypatch):
    monkeypatch.setattr(worker, "create_app", None)

    with pytest.raises(RuntimeError, match="Application factory"):
        worker.main(max_iterations=1)