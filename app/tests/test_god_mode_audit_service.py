#/home/srpihhllc/PlaidBridgeOpenBankingApi/app/tests/test_god_mode_audit_service.py

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import inspect

from app.extensions import db
from app.models.god_mode_audit_log import GodModeAuditLog
from app.services.god_mode_audit_service import GodModeAuditService


@pytest.fixture(autouse=True)
def clean_audit_logs(app):
    """Keep each test isolated."""
    with app.app_context():
        db.session.query(GodModeAuditLog).delete()
        db.session.commit()
        yield
        db.session.query(GodModeAuditLog).delete()
        db.session.commit()


def add_log(*, user_id, action, created_at, endpoint="/test"):
    record = GodModeAuditLog(
        user_id=user_id,
        action=action,
        endpoint=endpoint,
        created_at=created_at,
        metadata_json={"test": True},
    )
    db.session.add(record)
    db.session.commit()
    return record


def test_model_has_single_column_indexes(app):
    """The declared indexed columns should have database indexes."""
    with app.app_context():
        indexes = inspect(db.engine).get_indexes(GodModeAuditLog.__tablename__)
        indexed_columns = {
            column
            for index in indexes
            for column in index["column_names"]
        }

        assert {"created_at", "user_id", "action"} <= indexed_columns


def test_log_persists_record_and_request_details(app, monkeypatch):
    with app.test_request_context(
        "/operator/test",
        environ_base={"REMOTE_ADDR": "192.0.2.10"},
    ):
        monkeypatch.setattr(
            "app.services.god_mode_audit_service.current_user",
            SimpleNamespace(id=42),
        )

        record = GodModeAuditService.log(
            "settlement.override",
            metadata={"reason": "test"},
        )

        saved = db.session.get(GodModeAuditLog, record.id)
        assert saved is not None
        assert saved.user_id == 42
        assert saved.action == "settlement.override"
        assert saved.endpoint == "/operator/test"
        assert saved.ip_address == "192.0.2.10"
        assert saved.metadata_json == {"reason": "test"}


def test_log_uses_system_user_when_no_authenticated_user(app, monkeypatch):
    with app.test_request_context("/system/task"):
        monkeypatch.setattr(
            "app.services.god_mode_audit_service.current_user",
            None,
        )

        record = GodModeAuditService.log("system.task")

        assert record.user_id == 0
        assert record.endpoint == "/system/task"


def test_query_logs_filters_by_action_and_user(app):
    now = datetime.now(timezone.utc)
    add_log(user_id=7, action="reserve.release", created_at=now)
    add_log(user_id=7, action="settlement.override", created_at=now + timedelta(seconds=1))
    add_log(user_id=8, action="reserve.release", created_at=now + timedelta(seconds=2))

    results = GodModeAuditService.query_logs(
        action="reserve.release",
        user_id=7,
    )

    assert len(results) == 1
    assert results[0]["user_id"] == 7
    assert results[0]["action"] == "reserve.release"


def test_query_logs_orders_newest_first_and_paginates(app):
    now = datetime.now(timezone.utc)
    for index in range(5):
        add_log(
            user_id=1,
            action=f"action.{index}",
            created_at=now + timedelta(seconds=index),
        )

    results = GodModeAuditService.query_logs(limit=2, offset=1)

    assert [record["action"] for record in results] == ["action.3", "action.2"]


def test_query_logs_serializes_metadata_and_timestamp(app):
    timestamp = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    add_log(user_id=9, action="debug.toggle", created_at=timestamp)

    result = GodModeAuditService.query_logs()[0]

    assert result["metadata"] == {"test": True}
    assert result["created_at"] is not None
    assert result["action"] == "debug.toggle"
