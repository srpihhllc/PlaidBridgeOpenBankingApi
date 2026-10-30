#/home/srpihhllc/PlaidBridgeOpenBankingApi/app/tests/test_polsia_tasks.py

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.workers.polsia_tasks import (
    process_polsia_webhook_event,
    run_nightly_polsia_cycle,
)


def test_run_nightly_polsia_cycle_success():
    result = SimpleNamespace(model_dump=lambda: {"status": "ok"})

    mock_runner = MagicMock()
    mock_runner.trigger_night_task = AsyncMock(return_value=result)

    mock_client = MagicMock()
    mock_client.close = AsyncMock()

    with (
        patch(
            "app.workers.polsia_tasks.PolsiaClient",
            return_value=mock_client,
        ),
        patch(
            "app.workers.polsia_tasks.PolsiaNightCycleRunner",
            return_value=mock_runner,
        ),
    ):
        response = run_nightly_polsia_cycle.run(company_id="company-123")

    assert response == {"status": "ok"}
    mock_runner.trigger_night_task.assert_awaited_once_with(
        company_id="company-123",
        plaid_financial_summary={
            "status": "active",
            "trigger": "scheduled_night_beat",
        },
    )
    mock_client.close.assert_awaited_once()


def test_run_nightly_polsia_cycle_uses_default_company_id():
    result = SimpleNamespace(model_dump=lambda: {"status": "ok"})

    mock_runner = MagicMock()
    mock_runner.trigger_night_task = AsyncMock(return_value=result)

    mock_client = MagicMock()
    mock_client.close = AsyncMock()

    with (
        patch(
            "app.workers.polsia_tasks.PolsiaClient",
            return_value=mock_client,
        ),
        patch(
            "app.workers.polsia_tasks.PolsiaNightCycleRunner",
            return_value=mock_runner,
        ),
    ):
        response = run_nightly_polsia_cycle.run()

    assert response == {"status": "ok"}
    call = mock_runner.trigger_night_task.await_args
    assert call.kwargs["company_id"] == "comp_plaidbridge_01"
    mock_client.close.assert_awaited_once()


def test_run_nightly_polsia_cycle_retries_on_failure():
    failure = RuntimeError("Polsia unavailable")

    mock_runner = MagicMock()
    mock_runner.trigger_night_task = AsyncMock(side_effect=failure)

    mock_client = MagicMock()
    mock_client.close = AsyncMock()

    with (
        patch(
            "app.workers.polsia_tasks.PolsiaClient",
            return_value=mock_client,
        ),
        patch(
            "app.workers.polsia_tasks.PolsiaNightCycleRunner",
            return_value=mock_runner,
        ),
        patch.object(
            run_nightly_polsia_cycle,
            "retry",
            side_effect=RuntimeError("retry scheduled"),
        ) as mock_retry,
        pytest.raises(RuntimeError, match="retry scheduled"),
    ):
        run_nightly_polsia_cycle.run(company_id="company-123")

    mock_retry.assert_called_once_with(
        exc=failure,
        countdown=60,
    )
    mock_client.close.assert_awaited_once()


def test_process_polsia_webhook_completed():
    response = process_polsia_webhook_event.run(
        {
            "task_id": "task-1",
            "event": "task.completed",
            "payload": {"result": {"value": 42}},
        }
    )

    assert response == {
        "status": "processed",
        "task_id": "task-1",
    }


def test_process_polsia_webhook_failed():
    response = process_polsia_webhook_event.run(
        {
            "task_id": "task-2",
            "event": "task.failed",
            "payload": {"error": "connection failed"},
        }
    )

    assert response == {
        "status": "processed",
        "task_id": "task-2",
    }


def test_process_polsia_webhook_unknown_event():
    response = process_polsia_webhook_event.run(
        {
            "task_id": "task-3",
            "event": "task.started",
            "payload": {},
        }
    )

    assert response == {
        "status": "processed",
        "task_id": "task-3",
    }


def test_process_polsia_webhook_default_payload():
    response = process_polsia_webhook_event.run({})

    assert response == {
        "status": "processed",
        "task_id": None,
    }