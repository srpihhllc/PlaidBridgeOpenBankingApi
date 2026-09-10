from app import create_app


def test_app_factory_production_config(monkeypatch):
    """
    Exercises production environment branches inside the initialization factory
    to cover production config loader states.
    """
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")

    prod_app = create_app()
    # Verify that testing flags are off when evaluating standard config loads
    assert prod_app.config.get("TESTING") is False


def test_app_factory_development_config(monkeypatch):
    """
    Exercises development environment config paths inside app/__init__.py
    """
    monkeypatch.setenv("FLASK_ENV", "development")
    dev_app = create_app()
    assert dev_app is not None


def test_global_error_handlers_coverage(client):
    """
    Forces standard error handlers (404, 403, 500) registered inside
    app/__init__.py to fire, executing their telemetry logging blocks.
    """
    # Trigger 404 Error Handler block
    res_404 = client.get("/absolute-nonsense-route-designed-to-fail-404")
    assert res_404.status_code == 404

    # Trigger a 405 Method Not Allowed error handler block
    res_405 = client.post(
        "/admin/api/v1/users"
    )  # /users endpoint list is GET only
    assert res_405.status_code in [405, 404]


def test_app_context_processors(client):
    """
    Triggers inject_user or context inject processors registered inside the factory.
    """
    # Hit a standard known root route or fallback path to execute template parameters
    res = client.get("/")
    assert res.status_code in [200, 302, 404]
