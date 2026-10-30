# app/tests/test_email_routes.py

from unittest.mock import patch


def test_email_blueprint_is_registered(app):
    assert "email" in app.blueprints


def test_email_routes_are_registered(app):
    email_routes = {
        rule.rule
        for rule in app.url_map.iter_rules()
        if rule.endpoint.startswith("email.")
    }

    assert any(route.endswith("/send-test-email") for route in email_routes)
    assert any(route.endswith("/test-email-page") for route in email_routes)


def test_test_email_page(client):
    with patch(
        "app.blueprints.email_routes.render_template",
        return_value="<html>test email page</html>",
    ) as render_template:
        response = client.get("/test-email-page")

    assert response.status_code == 200
    assert response.get_data(as_text=True) == "<html>test email page</html>"
    render_template.assert_called_once_with("test_email.html")


def test_send_test_email_success(client):
    with patch("app.blueprints.email_routes.mail.send") as send:
        response = client.get("/send-test-email")

    assert response.status_code == 302
    send.assert_called_once()

    message = send.call_args.args[0]

    assert message.subject == "Hello from Flask!"
    assert "srpollardsihhllc@gmail.com" in message.recipients
    assert message.body == (
        "This is a test email sent from your Flask application."
    )


def test_send_test_email_failure(client):
    with patch(
        "app.blueprints.email_routes.mail.send",
        side_effect=RuntimeError("SMTP unavailable"),
    ):
        response = client.get("/send-test-email")

    assert response.status_code == 302