#/home/srpihhllc/PlaidBridgeOpenBankingApi/app/tests/test_sync_worker.py

from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import app.workers.sync_worker as worker


# ----------------------------------------------------------------------
# _get_extension() and _get_redis_client()
# ----------------------------------------------------------------------

def test_get_extension_returns_none_when_missing():
    assert worker._get_extension(SimpleNamespace(), "redis_client") is None


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
    def fake_import(name, *args, **kwargs):
        if name == "app.extensions":
            raise ImportError("Redis helper unavailable")
        return original_import(name, *args, **kwargs)

    import builtins

    original_import = builtins.__import__
    monkeypatch.setattr(builtins, "__import__", fake_import)

    assert worker._get_redis_client(SimpleNamespace()) is None


def test_get_redis_client_returns_none_when_helper_raises(monkeypatch):
    import app.extensions

    monkeypatch.setattr(
        app.extensions,
        "get_redis_client",
        MagicMock(side_effect=RuntimeError("Redis unavailable")),
        raising=False,
    )

    assert worker._get_redis_client(SimpleNamespace()) is None


# ----------------------------------------------------------------------
# _decode_job()
# ----------------------------------------------------------------------

@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (
            (b"sync:jobs", b'{"job_id": "123", "type": "plaid_transactions"}'),
            {"job_id": "123", "type": "plaid_transactions"},
        ),
        ('{"job_id": "123"}', {"job_id": "123"}),
        ((b"sync:jobs", b"not-json"), {"raw": "not-json"}),
        ("[1, 2, 3]", {"raw": [1, 2, 3]}),
        (bytearray(b'{"status": "ok"}'), {"status": "ok"}),
        (None, {"raw": None}),
    ],
)
def test_decode_job(value, expected):
    assert worker._decode_job(value) == expected


# ----------------------------------------------------------------------
# process_job()
# ----------------------------------------------------------------------

@pytest.fixture
def process_job_dependencies(monkeypatch):
    """Replace database, decryption, and ingestion dependencies."""
    from app.models import plaid_item
    from app.services import transaction_ingestion
    from app.utils import plaid_crypto

    if worker.create_app is None:
        pytest.fail("Flask application factory is unavailable")

    app = worker.create_app()

    with app.app_context():
        item = SimpleNamespace(plaid_access_token="encrypted-token")
        query = MagicMock()
        query.filter_by.return_value.first.return_value = item

        monkeypatch.setattr(plaid_item.PlaidItem, "query", query)

        decrypt = MagicMock(return_value="decrypted-token")
        sync = MagicMock(return_value=2)

        monkeypatch.setattr(plaid_crypto, "decrypt_token", decrypt)
        monkeypatch.setattr(
            transaction_ingestion,
            "sync_user_transactions_from_plaid",
            sync,
        )

        yield query, decrypt, sync, item


def test_process_job_syncs_transactions_from_stored_item(
    process_job_dependencies,
):
    query, decrypt, sync, item = process_job_dependencies

    result = worker.process_job(
        {
            "job_id": "job-1",
            "user_id": "user-1",
            "payload": {
                "type": "plaid_transactions",
                "plaid_item_id": "item-1",
            },
        }
    )

    assert result == 2
    query.filter_by.assert_called_once_with(
        user_id="user-1",
        plaid_item_id="item-1",
    )
    decrypt.assert_called_once_with(item.plaid_access_token)
    sync.assert_called_once_with(
        user_id="user-1",
        plaid_access_token="decrypted-token",
    )


def test_process_job_accepts_flat_payload(process_job_dependencies):
    query, _, _, _ = process_job_dependencies

    worker.process_job(
        {
            "job_id": "job-2",
            "type": "plaid_transactions",
            "user_id": "user-2",
            "plaid_item_id": "item-2",
        }
    )

    query.filter_by.assert_called_once_with(
        user_id="user-2",
        plaid_item_id="item-2",
    )


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({}, "Unsupported sync job type"),
        (
            {
                "type": "other",
                "user_id": "user-1",
                "plaid_item_id": "item-1",
            },
            "Unsupported sync job type",
        ),
        (
            {
                "type": "plaid_transactions",
                "plaid_item_id": "item-1",
            },
            "no valid user_id",
        ),
        (
            {
                "type": "plaid_transactions",
                "user_id": "user-1",
            },
            "no valid plaid_item_id",
        ),
    ],
)
def test_process_job_rejects_invalid_payload(payload, message):
    with pytest.raises(ValueError, match=message):
        worker.process_job(payload)


def test_process_job_raises_when_item_is_not_found(process_job_dependencies):
    query, decrypt, sync, _ = process_job_dependencies
    query.filter_by.return_value.first.return_value = None

    with pytest.raises(ValueError, match="Plaid item not found"):
        worker.process_job(
            {
                "job_id": "job-3",
                "user_id": "user-1",
                "payload": {
                    "type": "plaid_transactions",
                    "plaid_item_id": "missing-item",
                },
            }
        )

    decrypt.assert_not_called()
    sync.assert_not_called()



# ----------------------------------------------------------------------
# main()
# ----------------------------------------------------------------------

@contextmanager
def app_context():
    yield


def make_app(redis_client):
    return SimpleNamespace(
        redis_client=redis_client,
        app_context=app_context,
    )


def test_main_raises_when_create_app_is_unavailable(monkeypatch):
    monkeypatch.setattr(worker, "create_app", None)

    with pytest.raises(RuntimeError, match="Application factory"):
        worker.main(max_iterations=1)


def test_main_raises_when_redis_is_unavailable(monkeypatch):
    monkeypatch.setattr(worker, "create_app", lambda: SimpleNamespace())
    monkeypatch.setattr(worker, "_get_redis_client", lambda app: None)

    with pytest.raises(RuntimeError, match="Redis client unavailable"):
        worker.main(max_iterations=1)


def test_main_processes_job_inside_app_context(monkeypatch):
    redis = MagicMock()
    redis.blpop.return_value = (
        b"sync:jobs",
        b'{"job_id": "job-1"}',
    )
    app = make_app(redis)
    process = MagicMock()

    monkeypatch.setattr(worker, "create_app", lambda: app)
    monkeypatch.setattr(worker, "process_job", process)

    worker.main(max_iterations=1)

    redis.blpop.assert_called_once_with(
        worker.REDIS_LIST_KEY,
        timeout=worker.BLPOP_TIMEOUT,
    )
    process.assert_called_once_with({"job_id": "job-1"})


def test_main_sleeps_when_queue_is_empty(monkeypatch):
    redis = MagicMock()
    redis.blpop.return_value = None
    app = make_app(redis)
    sleep = MagicMock()

    monkeypatch.setattr(worker, "create_app", lambda: app)
    monkeypatch.setattr(worker.time, "sleep", sleep)

    worker.main(max_iterations=1)

    sleep.assert_called_once_with(worker.POLL_INTERVAL)


def test_main_retries_blpop_without_timeout_after_type_error(monkeypatch):
    redis = MagicMock()
    redis.blpop.side_effect = [TypeError("timeout unsupported"), None]
    app = make_app(redis)
    sleep = MagicMock()

    monkeypatch.setattr(worker, "create_app", lambda: app)
    monkeypatch.setattr(worker.time, "sleep", sleep)

    worker.main(max_iterations=1)

    assert redis.blpop.call_args_list == [
        ((worker.REDIS_LIST_KEY,), {"timeout": worker.BLPOP_TIMEOUT}),
        ((worker.REDIS_LIST_KEY,), {}),
    ]
    sleep.assert_called_once_with(worker.POLL_INTERVAL)


def test_main_continues_after_job_processing_fails(monkeypatch):
    redis = MagicMock()
    redis.blpop.return_value = (
        b"sync:jobs",
        b'{"job_id": "job-1"}',
    )
    app = make_app(redis)
    process = MagicMock(side_effect=RuntimeError("processing failed"))

    monkeypatch.setattr(worker, "create_app", lambda: app)
    monkeypatch.setattr(worker, "process_job", process)

    # The worker logs the processing exception and continues rather than raising.
    worker.main(max_iterations=1)

    process.assert_called_once_with({"job_id": "job-1"})


def test_main_stops_on_keyboard_interrupt(monkeypatch):
    redis = MagicMock()
    redis.blpop.side_effect = KeyboardInterrupt
    app = make_app(redis)

    monkeypatch.setattr(worker, "create_app", lambda: app)

    worker.main(max_iterations=None)
