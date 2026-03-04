"""
WSGI entry-point for PlaidBridgeOpenBankingApi.

Exposes ``application`` (uWSGI / PythonAnywhere) and ``app`` (gunicorn / Heroku).
"""

import logging
import os
import sys

_logger = logging.getLogger(__name__)

# Ensure the project root (this directory) is on sys.path so that
# ``import app`` resolves to the ``app/`` package next to this file.
_project_root = os.path.abspath(os.path.dirname(__file__))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from app import create_app, db  # noqa: E402

application = create_app()

with application.app_context():
    try:
        db.create_all()
    except Exception:
        _logger.warning("db.create_all() failed at startup; tables may already exist or DB may be unreachable", exc_info=True)

# Alias expected by the Procfile (``gunicorn wsgi:app``)
app = application
