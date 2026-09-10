# app/tests/sync_worker.py
import json
from unittest.mock import Mock, patch

import app.workers.sync_worker as sync_worker


def test_sync_worker_execution_success(app):
    """The worker decodes a Redis payload and processes it."""
    redis_client = Mock()
    payload = {
        "job_id": "job-123",
        "type": "transactions",
    }

    redis_client.blpop.return_value = (
        b"sync:jobs",
        json.dumps(payload).encode("utf-8"),
    )

    app.redis_client = redis_client

    with app.app_context():
        with (
            patch(
                "app.workers.sync_worker.create_app",
                return_value=app,
            ),
            patch("app.workers.sync_worker.process_job") as mock_process_job,
        ):
            sync_worker.main(max_iterations=1)

    redis_client.blpop.assert_called_once_with(
        sync_worker.REDIS_LIST_KEY,
        timeout=5,
    )
    mock_process_job.assert_called_once_with(payload)


def test_sync_worker_handles_invalid_json(app):
    """Invalid JSON is preserved as a raw payload instead of crashing."""
    redis_client = Mock()
    redis_client.blpop.return_value = (
        b"sync:jobs",
        b"not-valid-json",
    )

    app.redis_client = redis_client

    with app.app_context():
        with (
            patch(
                "app.workers.sync_worker.create_app",
                return_value=app,
            ),
            patch("app.workers.sync_worker.process_job") as mock_process_job,
        ):
            sync_worker.main(max_iterations=1)

    mock_process_job.assert_called_once_with(
        {
            "raw": "not-valid-json",
        }
    )


def test_sync_worker_handles_non_dict_json(app):
    """Valid JSON values that are not dictionaries are wrapped as raw data."""
    redis_client = Mock()
    redis_client.blpop.return_value = (
        b"sync:jobs",
        b"123",
    )

    app.redis_client = redis_client

    with app.app_context():
        with (
            patch(
                "app.workers.sync_worker.create_app",
                return_value=app,
            ),
            patch("app.workers.sync_worker.process_job") as mock_process_job,
        ):
            sync_worker.main(max_iterations=1)

    mock_process_job.assert_called_once_with(
        {
            "raw": 123,
        }
    )


def test_sync_worker_continues_after_job_processing_error(app):
    """A processing error is logged and does not terminate the worker."""
    redis_client = Mock()
    redis_client.blpop.return_value = (
        b"sync:jobs",
        b'{"job_id": "job-456", "type": "accounts"}',
    )

    app.redis_client = redis_client

    with app.app_context():
        with (
            patch(
                "app.workers.sync_worker.create_app",
                return_value=app,
            ),
            patch(
                "app.workers.sync_worker.process_job",
                side_effect=RuntimeError("processing failed"),
            ) as mock_process_job,
            patch("app.workers.sync_worker.logger.exception") as mock_logger,
        ):
            sync_worker.main(max_iterations=1)

    mock_process_job.assert_called_once_with(
        {
            "job_id": "job-456",
            "type": "accounts",
        }
    )
    mock_logger.assert_called_once_with("Job processing failed")


def test_sync_worker_handles_empty_queue(app):
    """An empty Redis response causes a polling sleep."""
    redis_client = Mock()
    redis_client.blpop.return_value = None

    app.redis_client = redis_client

    with app.app_context():
        with (
            patch(
                "app.workers.sync_worker.create_app",
                return_value=app,
            ),
            patch("app.workers.sync_worker.time.sleep") as mock_sleep,
            patch("app.workers.sync_worker.process_job") as mock_process_job,
        ):
            sync_worker.main(max_iterations=1)

    mock_sleep.assert_called_once_with(sync_worker.POLL_INTERVAL)
    mock_process_job.assert_not_called()


def test_sync_worker_runs_noop_without_redis(app):
    """Without Redis, the worker exits after the requested iteration count."""
    app.redis_client = None
    app.extensions = {}

    with app.app_context():
        with (
            patch(
                "app.workers.sync_worker.create_app",
                return_value=app,
            ),
            patch(
                "app.extensions.get_redis_client",
                return_value=None,
            ),
            patch("app.workers.sync_worker.time.sleep") as mock_sleep,
        ):
            sync_worker.main(max_iterations=2)

    assert mock_sleep.call_count == 2
    mock_sleep.assert_called_with(sync_worker.POLL_INTERVAL)


def test_sync_worker_uses_extension_redis_client(app):
    """The worker can obtain Redis from app.extensions."""
    redis_client = Mock()
    redis_client.blpop.return_value = (
        b"sync:jobs",
        b'{"job_id": "job-789"}',
    )

    app.redis_client = None
    app.extensions["redis_client"] = redis_client

    with app.app_context():
        with (
            patch(
                "app.workers.sync_worker.create_app",
                return_value=app,
            ),
            patch("app.workers.sync_worker.process_job") as mock_process_job,
        ):
            sync_worker.main(max_iterations=1)

    mock_process_job.assert_called_once_with(
        {
            "job_id": "job-789",
        }
    )
