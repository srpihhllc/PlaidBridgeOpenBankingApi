import pytest

from app import create_app
from app.config import probe_services


@pytest.fixture(scope="module")
def app():
    """Provide a Flask app context for running probe tests."""
    app = create_app()
    with app.app_context():
        yield app


def test_probes_services_strict(app):
    """
    Run probes in strict mode:
      • DB must respond to SELECT 1
      • Redis must respond to PING
    If either fails, probe_services will raise and CI will block merge.
    """
    result = probe_services(strict=True)
    assert result is None
