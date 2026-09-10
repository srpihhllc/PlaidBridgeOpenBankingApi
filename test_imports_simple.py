#/home/srpihhllc/PlaidBridgeOpenBankingApi/test_imports_simple.py

"""Model-import smoke tests."""

from __future__ import annotations

import os

os.environ.setdefault("FLASK_ENV", "testing")
os.environ.setdefault("TESTING", "True")
os.environ.setdefault("PYTEST", "True")
os.environ.setdefault("RATE_LIMIT_ENABLED", "False")


def test_user_model_import():
    from app.models.user import User

    assert User.__tablename__ == "users"
    assert User.__table_args__.get("extend_existing") is True


def test_access_token_model_import():
    from app.models.access_token import AccessToken

    assert AccessToken.__tablename__ == "access_tokens"
    assert AccessToken.__table_args__.get("extend_existing") is True
