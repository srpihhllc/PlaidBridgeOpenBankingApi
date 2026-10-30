from unittest.mock import Mock, patch

from app.admin.cockpit.trace.event_id import trace_detail


def test_trace_detail_returns_not_found_when_event_is_missing(app):
    redis_client = Mock()
    redis_client.get.return_value = None

    with app.test_request_context(
        "/admin/cockpit/trace/missing-event"
    ), patch(
        "app.admin.cockpit.trace.event_id.get_redis_client",
        return_value=redis_client,
    ), patch(
        "app.admin.cockpit.trace.event_id.render_template",
        return_value="not found page",
    ) as render_template:
        response, status_code = trace_detail.__wrapped__("missing-event")

    assert response == "not found page"
    assert status_code == 404

    redis_client.get.assert_called_once_with(
        "identity_event:missing-event"
    )
    render_template.assert_called_once_with(
        "cockpit/trace_not_found.html",
        event_id="missing-event",
    )


def test_trace_detail_renders_event_when_found(app):
    redis_client = Mock()
    redis_client.get.return_value = (
        b'{"event_id": "event-123", "status": "completed"}'
    )

    with app.test_request_context(
        "/admin/cockpit/trace/event-123"
    ), patch(
        "app.admin.cockpit.trace.event_id.get_redis_client",
        return_value=redis_client,
    ), patch(
        "app.admin.cockpit.trace.event_id.render_template",
        return_value="detail page",
    ) as render_template:
        response = trace_detail.__wrapped__("event-123")

    assert response == "detail page"

    redis_client.get.assert_called_once_with(
        "identity_event:event-123"
    )
    render_template.assert_called_once_with(
        "cockpit/trace_detail.html",
        event={
            "event_id": "event-123",
            "status": "completed",
        },
    )