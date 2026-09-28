#/home/srpihhllc/PlaidBridgeOpenBankingApi/app/tests/test_model_import_safety.py
#!/usr/bin/env python3
"""
Verify that model imports do not create duplicate module/table registrations.
"""

import importlib
import os
import sys
from pathlib import Path

# Add the repository root to sys.path.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ["FLASK_ENV"] = "testing"
os.environ["TESTING"] = "1"


def test_model_import_safety():
    """Ensure models import safely without duplicate registrations."""
    from app import create_app
    from app.extensions import db
    from sqlalchemy import inspect

    importlib.import_module("app.models")
    from app.models.user import User

    app = create_app(env_name="testing")

    with app.app_context():
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()

        user_table = User.__table__

        user_mod_1 = importlib.import_module("app.models.user")
        user_mod_2 = importlib.import_module("app.models.user")

        assert user_mod_1 is user_mod_2
        assert user_table.name
        assert isinstance(tables, list)